"""Sync labels and buttons use synthetic data; no external requests or writes."""
import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures, fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'sync-status-preview'


class SyncFixtures(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.rows = [dict(self.member, id=i, email=f'sync{i}@example.test', note='',
                          sub2_status=status, sub2_message=message)
                     for i, (status, message) in enumerate([
                         ('pending', 'Cookie 已写入，等待 Sub2 代理就绪'),
                         ('failed', 'Sub2 没有该账号，请先手动推送入库'),
                         ('pending', 'Cookie 已写入，等待重新验证'),
                         ('pending', '联动连接暂不可用，保留 Cookie 后重试'),
                         ('pending', '等待版本同步与验证'),
                         ('syncing', '正在同步 Cookie'),
                     ], 1)]

    async def serve(self, route):
        url = urlparse(route.request.url)
        assert url.netloc == 'sync.test', url.geturl()
        path = url.path.removeprefix(self.prefix)
        if path == '/api/external/groups':
            return await route.fulfill(json=[])
        if path == '/api/integration/sources':
            items = []
            for row in self.rows[:4]:
                verification = {1:'proxy_pending', 3:'verification_retry'}.get(row['id'])
                items.append(dict(source='外部子号', source_key=f"external:{row['id']}",
                                  email=row['email'], has_cookie=True, auto_recovery=True, version=1,
                                  delivery=dict(state='blocked' if row['sub2_status']=='failed' else 'retry',
                                                message=row['sub2_message'],
                                                receipt=dict(integration=dict(verification=verification)))))
            return await route.fulfill(json=dict(items=items, total=len(items)))
        return await super().serve(route)


async def check(browser, prefix, width, engine):
    context = await browser.new_context(viewport=dict(width=width, height=1000),
                                       locale='zh-CN', timezone_id='Asia/Shanghai')
    fixtures, errors = SyncFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-sync-status')")
    page = await context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    base = 'http://sync.test' + prefix
    await page.goto(base + '/external-members')
    await expect(page.locator('tr[data-member]')).to_have_count(6)
    button = page.locator('#extm-sub2-push')
    for mid, label in [(1,'等待代理'), (3,'等待验证'), (4,'等待重试'), (5,'等待同步'), (6,'Sub2 同步中…')]:
        row = page.locator(f'[data-member="{mid}"]')
        await expect(row).to_contain_text('Sub2 待同步' if mid==5 else label.rstrip('…'))
        await row.locator('.extm-rowck').check()
        await expect(button).to_be_disabled()
        await expect(button).to_have_text(label)
        if mid==6:
            await expect(button).to_have_class(re.compile('.*n-button--loading.*'))
        else:
            await expect(button).not_to_have_class(re.compile('.*n-button--loading.*'))
        await row.locator('.extm-rowck').uncheck()
    failed = page.locator('[data-member="2"]')
    await expect(failed).to_contain_text('Sub2 同步失败')
    await expect(failed).to_contain_text('Sub2 没有该账号，请先手动推送入库')
    await failed.locator('.extm-rowck').check()
    await expect(button).to_be_enabled()
    await failed.locator('.extm-rowck').uncheck()
    waiting = page.locator('[data-member="1"]')
    await waiting.locator('[data-sub2-details]').click()
    await expect(page.locator('#extm-sub2-detail-dialog')).to_contain_text('等待代理')
    await page.locator('#extm-sub2-detail-dialog button').click()
    # Polling must also replace a queued button after a no-ID failure.
    await waiting.locator('.extm-rowck').check()
    fixtures.rows[0].update(sub2_status='failed', sub2_message='联动密钥无效或无权操作，请检查配置')
    await expect(waiting).to_contain_text('联动密钥无效或无权操作', timeout=7000)
    await expect(button).to_be_enabled()
    await expect(button).not_to_contain_text('同步中')
    fixtures.rows[0].update(sub2_status='pending', sub2_message='Cookie 已写入，等待 Sub2 代理就绪')
    await page.locator('#extm-refresh').click()
    await expect(button).to_have_text('等待代理')
    await expect(page.locator('#extm-refresh')).not_to_have_class(re.compile('.*n-button--loading.*'))
    await fits(page, '#extm-embed')
    await page.screenshot(path=str(OUTPUT/f'{engine}-{prefix.strip("/") or "root"}-{width}.png'), full_page=True)
    await page.goto(base + '/integration')
    for email, label in [('sync1','等待代理'), ('sync2','同步失败'), ('sync3','等待验证'), ('sync4','等待重试')]:
        row = page.locator('#integration-sources tr').filter(has_text=email+'@example.test')
        await expect(row).to_contain_text(label)
    await expect(page.locator('#integration-sources')).to_contain_text('Sub2 没有该账号，请先手动推送入库')
    await page.evaluate("document.documentElement.classList.add('dark')")
    await fits(page, '#integration-panel')
    assert not fixtures.writes and not fixtures.escaped and not errors, (fixtures.writes,fixtures.escaped,errors)
    await context.close()
    print(f'PASS {engine} {prefix or "/"} {width}: proxy/verify/retry/queue/failure labels and polling', flush=True)


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    engine = os.environ.get('SYNC_BROWSER', 'chromium')
    async with async_playwright() as p:
        browser = await getattr(p, engine).launch()
        for prefix in ('', '/okad'):
            for width in (1440, 390):
                await check(browser, prefix, width, engine)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
