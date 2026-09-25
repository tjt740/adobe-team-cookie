"""Verify export scope and downloaded JSON with synthetic data only."""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    rows = [dict(id=i, email=f'account{i}@example.com', login_status='never',
                 has_cookie=i != 3, subscription_ok=False, created_at='2026-09-24T00:00:00')
            for i in range(1, 4)]
    requests = []
    reject = False

    async def route_api(route):
        nonlocal reject
        req = route.request
        url = urlparse(req.url)
        if url.path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif url.path == '/api/external/members':
            data = dict(items=rows, total=len(rows))
        elif url.path == '/api/external/members/export':
            requests.append((req.method, req.post_data_json if req.method == 'POST' else parse_qs(url.query)))
            await asyncio.sleep(.2)
            if reject:
                await route.fulfill(status=503, json={'detail': '模拟导出失败'})
                return
            ids = req.post_data_json['ids'] if req.method == 'POST' else [1, 2, 3]
            data = [{'cookie': f'test={i}'} for i in ids if i != 3]
        elif url.path == '/api/settings':
            data = {'concurrency': 2}
        elif url.path == '/api/adobe-accounts/jobs':
            data = []
        else:
            data = {'items': [], 'total': 0, 'page': 1, 'size': 20}
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors, downloads = [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('download', lambda d: downloads.append(d))
        await page.route('**/api/**', route_api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/adobe')
        await page.locator('#extm-nav').click()
        await expect(page.locator('tr[data-member]')).to_have_count(3)
        button = page.locator('#extm-export')
        await expect(button).to_have_text('导出全部 Cookie')
        await page.locator('[data-member="2"] .extm-rowck').check()
        await page.locator('[data-member="3"] .extm-rowck').check()
        await expect(button).to_have_text('导出选中 Cookie（2）')
        async with page.expect_download() as downloading:
            await button.click()
            await expect(button).to_be_disabled()
        download = await downloading.value
        assert json.loads(Path(await download.path()).read_text()) == [{'cookie': 'test=2'}]
        assert requests[-1] == ('POST', {'ids': [2, 3]})
        await expect(page.locator('#extm-op')).to_contain_text('跳过 1 个')
        await expect(button).to_be_enabled()
        await page.locator('[data-member="2"] .extm-rowck').uncheck()
        await button.click()
        await expect(page.locator('#extm-op')).to_have_text('选中账号暂无可导出的 Cookie')
        assert len(downloads) == 1
        await page.locator('#extm-ckall').check()
        await expect(button).to_have_text('导出选中 Cookie（3）')
        await page.locator('#extm-ckall').uncheck()
        async with page.expect_download():
            await button.click()
        assert requests[-1] == ('GET', {})
        await page.locator('#extm-f-kw').fill('account')
        await page.locator('#extm-f-status').select_option('ok')
        await page.locator('#extm-f-sub').select_option('true')
        await expect(button).to_have_text('导出筛选 Cookie')
        async with page.expect_download():
            await button.click()
        assert requests[-1] == ('GET', {'keyword': ['account'], 'login_status': ['ok'], 'subscription_ok': ['true']})
        await expect(button).to_be_enabled()
        reject = True
        await page.locator('[data-member="1"] .extm-rowck').check()
        await button.click()
        await expect(page.locator('#extm-op')).to_have_text('模拟导出失败')
        await expect(button).to_be_enabled()
        await expect(button).to_have_text('导出选中 Cookie（1）')
        assert len(downloads) == 3
        assert not errors, errors
        await browser.close()
    print('PASS: selected download contents, empty cookies, select all, filters, failure recovery')


if __name__ == '__main__':
    asyncio.run(main())
