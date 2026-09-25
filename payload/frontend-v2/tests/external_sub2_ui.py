"""Selected external push and its independent sync state, with mocked APIs."""
import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    rows = [dict(id=i, email=f'external{i}@example.com', login_status='ok',
                 has_cookie=True, subscription_ok=True, created_at='2026-09-26T00:00:00',
                 sub2_status='not_pushed', message='登录成功') for i in (1, 2)]
    pushes = []
    reject = False
    stock_ids = set()
    stock_ok = True
    configured = True
    stock_reads = 0

    async def route_api(route):
        nonlocal reject, stock_reads
        req = route.request
        path = urlparse(req.url).path
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/external/members':
            data = dict(items=rows, total=2)
        elif path == '/api/external/members/sub2-stock':
            stock_reads += 1
            data = dict(ok=stock_ok, configured=configured, checked_at='2026-09-26T01:00:00Z',
                        message='' if stock_ok else 'Sub2 连接失败',
                        items={r['id']: dict(email=r['email'], in_stock=r['id'] in stock_ids,
                                            account_ids=[r['id'] + 10] if r['id'] in stock_ids else []) for r in rows} if stock_ok else {})
        elif path == '/api/external/members/push-sub2':
            pushes.append(req.post_data_json['ids'])
            await asyncio.sleep(.3)
            if reject:
                await route.fulfill(status=400, json={'detail': '请先选择 Adobe 分组'})
                return
            rows[0].update(sub2_status='pending', sub2_message='等待同步 Cookie')
            data = dict(queued=1, skipped=0, message='已提交 1 个账号同步')
        elif path == '/api/adobe-accounts/jobs':
            data = []
        elif path == '/api/settings':
            data = {'concurrency': 2}
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/api/**', route_api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/dashboard')
        await page.locator('#extm-nav').click()
        button = page.locator('#extm-sub2-push')
        await expect(button).to_be_disabled()
        first = page.locator('[data-member="1"] [data-sub2-stock]')
        second = page.locator('[data-member="2"] [data-sub2-stock]')
        await expect(first).to_have_text('未在库 Sub2')
        # Another entry point imports both accounts. No click or reload here:
        # polling must update the badges without sending either account again.
        stock_ids.update([1, 2])
        await expect(first).to_have_text('在库 Sub2', timeout=6000)
        await expect(second).to_have_text('在库 Sub2')
        assert pushes == [] and all(r['sub2_status'] == 'not_pushed' for r in rows)
        await page.locator('[data-member="1"] .extm-rowck').check()
        await expect(button).to_be_enabled()
        await button.click()
        await expect(button).to_be_disabled()
        await expect(page.locator('[data-member="1"]')).to_contain_text('Sub2 待同步')
        assert pushes == [[1]]
        rows[0].update(sub2_status='synced', sub2_account_id=12, sub2_synced_at='2026-09-26T01:00:00Z')
        await page.locator('#extm-refresh').click()
        await expect(first).to_have_text('在库 Sub2')
        await expect(first).to_have_attribute('title', re.compile('Cookie 上次同步成功'))
        await expect(second).not_to_have_attribute('title', re.compile('Cookie 上次同步成功'))
        await expect(button).to_be_enabled()
        rows[0].update(sub2_status='failed', sub2_message='Sub2 管理员密钥无效（HTTP 401）')
        await page.locator('#extm-refresh').click()
        await expect(page.locator('[data-member="1"]')).to_contain_text('Sub2 同步失败')
        await expect(page.locator('[data-member="1"]')).to_contain_text('管理员密钥无效')
        await expect(page.locator('[data-member="1"]')).to_contain_text('登录成功')
        reject = True
        await button.click()
        await expect(page.locator('#extm-op')).to_contain_text('请先选择 Adobe 分组')
        await expect(button).to_be_enabled()
        stock_ids.remove(2)
        await expect(second).to_have_text('未在库 Sub2', timeout=6000)
        stock_ok = False
        await expect(first).to_have_text('Sub2 状态暂不可用', timeout=6000)
        await expect(second).to_have_text('Sub2 状态暂不可用')
        configured = False
        await page.locator('#extm-refresh').click()
        await expect(first).to_have_text('Sub2 未配置')
        configured = True
        stock_ok = True
        await page.locator('#extm-refresh').click()
        await expect(first).to_have_text('在库 Sub2')
        # Changing pages stops the stock poll; reopening checks immediately.
        await page.locator('a[href="/settings"]').click()
        await page.wait_for_timeout(300)
        before = stock_reads
        await page.wait_for_timeout(3300)
        assert stock_reads == before
        stock_ids.clear()
        await page.locator('#extm-nav').click()
        await expect(first).to_have_text('未在库 Sub2')
        await page.screenshot(path=str(Path(__file__).resolve().parents[3] / '.local/external-sub2-sync-ui.png'), full_page=True)
        assert not errors, errors
        await browser.close()
    print('PASS: remote inventory auto-refresh, deletion/outage/configuration changes, read-only cross-entry status, sync history, selected push and retries')


if __name__ == '__main__':
    asyncio.run(main())
