"""External row mail reader: local assets, synthetic mail APIs, no real credentials."""
import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures, dialog_fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'external-mail-preview'


class MailFixtures(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.rows = [dict(self.member, id=i, email=f'reader{i}@example.test') for i in (1, 2)]
        self.mode, self.detail_error, self.detail_delay = 'supply', False, False
        self.reads = []

    async def serve(self, route):
        url = urlparse(route.request.url)
        path = url.path.removeprefix(self.prefix)
        if path == '/api/external/groups':
            return await route.fulfill(json=[])
        if path.endswith('/mail/message'):
            query = parse_qs(url.query)
            self.reads.append((path, query))
            if self.detail_delay:
                await asyncio.sleep(.5)
            if self.detail_error:
                return await route.fulfill(status=400, json=dict(detail='邮件正文读取失败，请重试'))
            return await route.fulfill(json=dict(subject='完整主题', sender='adobe@example.test',
                recipient='reader1@example.test', date='2026-10-24T04:00:00Z',
                body='完整邮件正文：验证码 654321\n<img src=x onerror=alert(1)>\n' + '很长的邮件内容' * 250))
        if path.endswith('/mail'):
            self.reads.append((path, {}))
            if self.mode == 'error':
                return await route.fulfill(status=400, json=dict(detail='supply.ink Token 已失效'))
            if self.mode == 'malformed':
                return await route.fulfill(json=dict(messages=None))
            messages = []
            if self.mode == 'supply':
                messages = [dict(id='1', subject='Adobe 验证码', sender='adobe@example.test',
                    date='2026-10-24T04:00:00Z', body='验证码 123456\n<img src=x onerror=alert(1)>'),
                    dict(id='2', subject='第二封邮件', body='另一封邮件的正文')]
            elif self.mode in ('imap', 'graph', 'moemail'):
                messages = [dict(id='Junk|message/+=42', subject='Adobe 验证码', preview='预览没有完整验证码')]
            return await route.fulfill(json=dict(source=self.mode, source_label='测试邮箱', messages=messages))
        return await super().serve(route)


async def scenario(browser, prefix, width):
    context = await browser.new_context(viewport=dict(width=width, height=900 if width > 600 else 812),
                                        timezone_id='Asia/Shanghai', locale='zh-CN')
    fixtures, errors = MailFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-mail-reader')")
    page = await context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto('http://mail.test' + prefix + '/external-members')
    await expect(page.locator('tr[data-member="1"]')).to_be_visible()
    trigger = page.locator('[data-row-more="1"],tr[data-member="1"] [data-mail]')

    async def open_mail(member_id=1):
        menu_trigger = page.locator(f'[data-row-more="{member_id}"]')
        if await menu_trigger.count():
            await menu_trigger.click()
            await page.locator(f'#extm-row-menu [data-mail="{member_id}"]').click()
            await expect(page.locator('#extm-row-menu')).not_to_be_visible()
        else:
            await page.locator(f'tr[data-member="{member_id}"] [data-mail]').click()
        await expect(page.locator('#extm-mail-dialog')).to_be_visible()

    await open_mail()
    dialog = page.locator('#extm-mail-dialog')
    await expect(dialog.locator('[data-mail-account]')).to_have_text('reader1@example.test')
    await expect(dialog.locator('pre').first).to_be_visible()
    await expect(dialog.locator('pre').first).to_contain_text('123456')
    await expect(dialog.locator('.extm-mail-meta').first).to_contain_text('adobe@example.test')
    assert await dialog.locator('img,iframe,script').count() == 0
    await dialog.locator('summary').nth(1).click()
    await expect(dialog.locator('pre').nth(1)).to_be_visible()
    await expect(dialog.locator('pre').nth(1)).to_have_text('另一封邮件的正文')
    await dialog_fits(page, '#extm-mail-dialog')
    await page.keyboard.press('Escape')
    await expect(dialog).to_have_count(0)
    await expect(trigger).to_be_focused()

    # Summaries must retrieve the full body, preserving opaque provider IDs and source.
    for source in ('imap', 'graph', 'moemail'):
        fixtures.mode = source
        fixtures.detail_error = source == 'imap'
        await open_mail()
        if fixtures.detail_error:
            await expect(dialog.locator('pre')).to_contain_text('正文读取失败')
            fixtures.detail_error = False
            await dialog.get_by_role('button', name='重试读取正文').click()
        await expect(dialog.locator('pre')).to_contain_text('完整邮件正文：验证码 654321')
        assert fixtures.reads[-1][1] == dict(source=[source], message_id=['Junk|message/+=42'])
        await expect(dialog.locator('summary')).to_contain_text('完整主题')
        assert await dialog.locator('img,iframe,script').count() == 0
        await dialog_fits(page, '#extm-mail-dialog')
        await expect(dialog.get_by_role('button', name='关闭', exact=True)).to_be_in_viewport()
        if source == 'graph' and not prefix:
            await page.screenshot(path=str(OUTPUT / f'mail-{width}.png'))
        await dialog.locator('[data-close]').click()

    # Empty, expired-token and invalid response states remain refreshable.
    fixtures.mode = 'empty'
    await open_mail()
    await expect(dialog.locator('[data-mail-status]')).to_contain_text('暂无邮件')
    for mode, message in [('error', 'Token 已失效'), ('malformed', '邮件列表格式无效'), ('supply', '最近 2 封')]:
        fixtures.mode = mode
        await dialog.locator('[data-refresh]').click()
        await expect(dialog.locator('[data-mail-status]')).to_contain_text(message)
        await expect(dialog.locator('[data-refresh]')).to_be_enabled()
    await dialog.locator('[data-close]').click()

    # Closing an in-flight body read must not affect a subsequently opened account.
    fixtures.mode, fixtures.detail_delay = 'imap', True
    await open_mail()
    await expect(dialog.locator('pre')).to_contain_text('正在读取邮件正文')
    fixtures.mode = 'supply'
    await dialog.locator('[data-refresh]').click()
    await expect(dialog.locator('pre').first).to_contain_text('123456')
    await dialog.locator('[data-close]').click()
    fixtures.mode = 'imap'
    await open_mail()
    await expect(dialog.locator('pre')).to_contain_text('正在读取邮件正文')
    await dialog.locator('[data-close]').click()
    await expect(dialog).to_have_count(0)
    fixtures.mode, fixtures.detail_delay = 'supply', False
    await open_mail(2)
    await expect(dialog.locator('[data-mail-account]')).to_have_text('reader2@example.test')
    await expect(dialog.locator('pre').first).to_contain_text('123456')
    await dialog.locator('[data-close]').click()

    await page.evaluate("localStorage.setItem('okad-theme','dark')")
    await page.reload()
    await open_mail()
    await expect(dialog.locator('pre').first).to_contain_text('123456')
    await dialog_fits(page, '#extm-mail-dialog')
    assert await dialog.evaluate("el=>getComputedStyle(el).backgroundColor") != 'rgb(255, 255, 255)'
    if not prefix:
        await page.screenshot(path=str(OUTPUT / f'mail-dark-{width}.png'))
    await dialog.locator('[data-close]').click()
    assert not fixtures.escaped, fixtures.escaped
    assert not errors, errors
    await context.close()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('MAIL_BROWSER', 'chromium')).launch()
        for prefix in ('', '/okad'):
            for width in (1440, 390):
                await scenario(browser, prefix, width)
        await browser.close()
    print('External row mail reader passed: full bodies, source selection, retries, refresh, close, mobile and mounted routes')


if __name__ == '__main__':
    asyncio.run(main())
