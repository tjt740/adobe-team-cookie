"""Mailbox import provenance and required options, with synthetic APIs on both mounts."""
import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures, fits, dialog_fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'email-import-preview'


class EmailFixtures(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.mail = [dict(id=i, email=f'mail{i}@example.test', password='', refresh_token='',
                          client_id='', mail_url='', remark='', is_used=i == 1,
                          import_batch='20261024' if i == 1 else '20261025',
                          imported_at='2026-10-24T04:05:06', created_at='2026-10-24T04:05:06') for i in (1, 2)]
        self.queries = []
        self.fail_import = False

    async def serve(self, route):
        url = urlparse(route.request.url)
        path = url.path.removeprefix(self.prefix)
        if path == '/api/emails/import-batches':
            return await route.fulfill(json=['20261025', '20261024'])
        if path.startswith('/api/emails'):
            if route.request.method == 'GET':
                query = parse_qs(url.query)
                self.queries.append(query)
                rows = self.mail
                if query.get('import_batch'):
                    rows = [r for r in rows if r['import_batch'] == query['import_batch'][0]]
                if query.get('is_used'):
                    rows = [r for r in rows if r['is_used'] == (query['is_used'][0] == 'true')]
                return await route.fulfill(json=dict(items=rows, total=len(rows)))
            data = route.request.post_data_json
            self.writes.append((path, data))
            if self.fail_import:
                return await route.fulfill(status=503, json={'detail': '模拟导入失败'})
            if path in ('/api/emails/batch-import', '/api/emails/moemail/generate'):
                return await route.fulfill(json=dict(created=1, updated=0, skipped=0, failed=0, errors=[]))
            return await route.fulfill(json={**self.mail[0], **data})
        return await super().serve(route)


async def choose(page, control, label):
    await control.locator('.n-base-selection').click()
    await page.locator('.n-base-select-option:visible').filter(has=page.get_by_text(label, exact=True)).click()
    await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)


async def check(browser, prefix, width):
    context = await browser.new_context(viewport=dict(width=width, height=1000 if width > 800 else 844), locale='zh-CN')
    fixtures, errors = EmailFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-mail')")
    page = await context.new_page()
    page.set_default_timeout(10000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto('http://mail.test'+prefix+'/email')
    ws = page.locator('#email-workspace')
    await expect(ws).to_contain_text('mail1@example.test')
    await expect(ws.locator('th').get_by_text('导入批次', exact=True)).to_have_count(1)
    await expect(ws.locator('th').get_by_text('导入时间', exact=True)).to_have_count(1)
    await expect(ws).to_contain_text('2026-10-24 12:05:06')
    if width <= 800:
        await ws.get_by_role('button', name='筛选条件').click()
    batch_filter = ws.locator('.ws-field').filter(has=page.get_by_text('导入批次', exact=True))
    await choose(page, batch_filter, '20261024')
    await expect(ws).not_to_contain_text('mail2@example.test')
    assert fixtures.queries[-1]['import_batch'] == ['20261024']
    await choose(page, ws.locator('.ws-field').filter(has=page.get_by_text('使用状态', exact=True)), '已使用')
    assert fixtures.queries[-1]['is_used'] == ['true']
    await ws.get_by_role('button', name='重置', exact=True).click()
    await expect(ws).to_contain_text('mail2@example.test')
    assert 'import_batch' not in fixtures.queries[-1]
    await fits(page, '#email-workspace')

    await ws.get_by_role('button', name='批量导入', exact=True).click()
    drawer = page.locator('.ws-import-drawer')
    content = drawer.get_by_role('textbox', name='账号内容识别')
    await content.fill('batch@example.test----pass')
    await drawer.get_by_role('button', name='开始导入').click()
    await expect(drawer.get_by_role('alert')).to_have_text('请选择导入批次')
    assert not fixtures.writes
    await drawer.get_by_label('导入批次', exact=True).fill('2026-10-24')
    await expect(drawer).to_contain_text('批次：20261024')
    await drawer.get_by_role('button', name='开始导入').click()
    await expect(drawer.get_by_role('alert')).to_have_text('请选择重复邮箱操作')
    assert not fixtures.writes
    await choose(page, drawer.locator('.ws-email-import-field').nth(1), '覆盖更新')
    await drawer.get_by_role('button', name='关闭', exact=True).click()
    await ws.get_by_role('button', name='批量导入', exact=True).click()
    await expect(content).to_have_value('batch@example.test----pass')
    await expect(drawer.get_by_label('导入批次', exact=True)).to_have_value('2026-10-24')
    fixtures.fail_import = True
    await drawer.get_by_role('button', name='开始导入').click()
    await expect(drawer.get_by_role('alert')).to_have_text('模拟导入失败')
    await expect(content).to_have_value('batch@example.test----pass')
    fixtures.fail_import = False
    await drawer.get_by_role('button', name='开始导入').click()
    await expect(drawer.get_by_role('status')).to_contain_text('新增 1')
    assert fixtures.writes[-1][1] == dict(content='batch@example.test----pass', on_duplicate='overwrite', import_batch='20261024')
    await expect(content).to_have_value('')
    await dialog_fits(page, '.ws-import-drawer')
    await expect(page.locator('.n-message')).to_have_count(0)
    if width <= 800:
        await page.set_viewport_size(dict(width=320, height=360))
        await dialog_fits(page, '.ws-import-drawer')
        box = await drawer.get_by_role('button', name='开始导入').bounding_box()
        assert box['y'] >= 0 and box['y'] + box['height'] <= 361, box
        await page.set_viewport_size(dict(width=width, height=844))
    if not prefix:
        await page.screenshot(path=str(OUTPUT/f'batch-{width}.png'), animations='disabled')
    await drawer.get_by_role('button', name='关闭', exact=True).click()

    await ws.get_by_role('button', name='新增邮箱', exact=True).click()
    single = page.locator('.ws-drawer:visible')
    await single.get_by_placeholder('example@outlook.com').fill('single@example.test')
    count = len(fixtures.writes)
    await single.get_by_role('button', name='保存', exact=True).click()
    await expect(page.locator('.n-message').last).to_contain_text('请选择导入批次')
    assert len(fixtures.writes) == count
    await single.get_by_label('导入批次', exact=True).fill('2026-10-25')
    await single.get_by_role('button', name='保存', exact=True).click()
    await expect(page.locator('.n-message').last).to_contain_text('请选择重复邮箱操作')
    assert len(fixtures.writes) == count
    await choose(page, single.locator('.ws-email-import-field').nth(1), '跳过')
    await dialog_fits(page, '.ws-drawer:visible')
    await expect(page.locator('.n-message')).to_have_count(0)
    if not prefix:
        await page.screenshot(path=str(OUTPUT/f'single-{width}.png'), animations='disabled')
    await single.get_by_role('button', name='保存', exact=True).click()
    await expect(single).not_to_be_visible()
    assert fixtures.writes[-1][1]['import_batch'] == '20261025'
    assert fixtures.writes[-1][1]['on_duplicate'] == 'skip'

    await ws.get_by_role('button', name='编辑', exact=True).first.click()
    await expect(page.get_by_label('导入批次', exact=True)).to_have_count(0)
    await page.get_by_role('button', name='保存', exact=True).click()
    assert 'import_batch' not in fixtures.writes[-1][1] and 'on_duplicate' not in fixtures.writes[-1][1]

    await ws.get_by_role('button', name='创建 MoeMail', exact=True).click()
    moe = page.locator('.ws-drawer:visible')
    await moe.get_by_label('导入批次', exact=True).fill('2026-10-25')
    await choose(page, moe.locator('.ws-email-import-field').nth(1), '覆盖更新')
    await moe.get_by_role('button', name='创建', exact=True).click()
    await expect(moe).not_to_be_visible()
    assert fixtures.writes[-1][0] == '/api/emails/moemail/generate'
    assert fixtures.writes[-1][1]['import_batch'] == '20261025'

    await page.evaluate("localStorage.setItem('okad-theme','dark')")
    await page.reload()
    await ws.get_by_role('button', name='批量导入', exact=True).click()
    drawer = page.locator('.ws-import-drawer')
    assert await drawer.evaluate('e=>getComputedStyle(e).backgroundColor') != 'rgb(255, 255, 255)'
    await drawer.get_by_label('导入批次', exact=True).fill('2026-10-24')
    await dialog_fits(page, '.ws-import-drawer')
    if not prefix:
        await page.screenshot(path=str(OUTPUT/f'dark-{width}.png'), animations='disabled')
    assert not errors, errors
    assert not fixtures.escaped, fixtures.escaped
    await context.close()


async def main():
    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('MAIL_BROWSER', 'chromium')).launch()
        for prefix in ('', '/okad'):
            for width in (1440, 390):
                await check(browser, prefix, width)
                print(f'PASS mailbox batches {prefix or "/"} {width}px', flush=True)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
