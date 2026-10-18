"""Subscription warnings, safe details and recovery, with synthetic API responses."""
import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18082')


async def main():
    rows = [dict(id=i, email=f'preview{i}@example.test', login_status='ok',
                 first_login_done=True, has_cookie=True, credits_available=None,
                 credits_total=None, subscription_ok=False, message='登录成功',
                 created_at='2026-10-10T06:00:00Z', last_login_at='2026-10-10T06:04:00Z')
            for i in range(1, 7)]
    rows[0]['credits_error'] = 'Adobe 拒绝查询（HTTP 451 / 10009）'
    rows[2].update(credits_available=0, credits_total=4000, subscription_ok=True)
    rows[3].update(credits_available=0, credits_total=0)
    rows[4].update(login_status='never', first_login_done=False, has_cookie=False, last_login_at=None)
    rows[5]['credits_error'] = '<img src=x onerror=alert(1)>模拟异常'
    writes = []

    async def api(route):
        req = route.request
        if req.method != 'GET':
            writes.append(req.method); await route.abort(); return
        path = urlparse(req.url).path.removeprefix('/okad')
        if path == '/api/auth/me':
            data = dict(id=1, username='preview', is_superuser=True, is_active=True)
        elif path == '/api/external/members':
            data = dict(items=rows, total=len(rows))
        elif path == '/api/external/members/sub2-stock':
            data = dict(ok=True, configured=False, items={})
        elif path == '/api/adobe-accounts/jobs':
            data = []
        elif path == '/api/settings':
            data = dict(concurrency=2)
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport=dict(width=2560, height=1100))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.route('**/api/**', api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-credit-test')")
        await page.goto(BASE + '/external-members', wait_until='networkidle')
        cell = lambda i: page.locator(f'[data-member="{i}"] [data-subscription]')
        await expect(cell(1)).to_contain_text('积分查询失败')
        await expect(cell(1).locator('button')).to_have_attribute('title', re.compile('HTTP 451 / 10009'))
        await expect(page.locator('[data-member="1"] .extm-status')).to_contain_text('登录成功')
        await expect(cell(2)).to_contain_text('积分未查到')
        await expect(cell(2).locator('button')).to_have_attribute('title', re.compile('订阅状态未知'))
        await expect(cell(2)).to_have_text('积分未查到')
        await expect(cell(3)).to_have_text('订阅正常')
        await expect(cell(4)).to_have_text('掉订阅')
        await expect(cell(5)).to_have_text('待查询')
        await cell(1).locator('button').click()
        dialog = page.locator('#extm-credit-dialog')
        await expect(dialog).to_contain_text('Adobe 拒绝查询（HTTP 451 / 10009）')
        await expect(dialog).to_contain_text('不代表积分为 0 或已掉订阅')
        await expect(dialog).to_contain_text('重登')
        await dialog.get_by_role('button', name='知道了').click()
        await expect(cell(1).locator('button')).to_be_focused()
        await cell(2).locator('button').click()
        await expect(dialog).to_contain_text('历史记录未保存具体失败原因')
        await page.keyboard.press('Escape')
        await cell(6).locator('button').click()
        await expect(dialog).to_contain_text('<img src=x onerror=alert(1)>')
        assert await dialog.locator('img').count() == 0
        await page.keyboard.press('Escape')
        for width in (2560, 1440, 1100):
            await page.set_viewport_size(dict(width=width, height=1100))
            await cell(1).scroll_into_view_if_needed()
            bounds = await cell(1).evaluate('(el) => ({cell:el.getBoundingClientRect().width, content:el.querySelector("button").getBoundingClientRect().width})')
            assert bounds['content'] + 24 <= bounds['cell'], bounds
        await page.set_viewport_size(dict(width=2560, height=1100))
        await page.screenshot(path=str(ROOT / '.local/credits-error-preview.png'), full_page=True)
        rows[0].update(credits_error='', credits_available=3620, credits_total=4000, subscription_ok=True)
        await page.locator('#extm-refresh').click()
        await expect(cell(1)).to_have_text('订阅正常')
        await expect(cell(1).locator('button')).to_have_count(0)
        assert not writes and not errors, (writes, errors)
        await browser.close()
    print('PASS: subscription warnings, safe details, old records, zero balance, recovery and layout')


if __name__ == '__main__':
    asyncio.run(main())
