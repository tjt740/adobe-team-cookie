"""Verify selection, downloaded Excel bytes and error recovery with synthetic data."""
import asyncio
from io import BytesIO
import os
from pathlib import Path
import sys
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'payload/backend'))
from app.services.email_export import emails_xlsx, XLSX_MEDIA_TYPE

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    rows = [dict(id=i, email=f'account{i}@example.com', login_status='login_failed',
                 has_cookie=False, subscription_ok=False, created_at='2026-10-12T00:00:00')
            for i in range(1, 4)]
    requests, downloads, errors = [], [], []
    reject = 0

    async def api(route):
        path = urlparse(route.request.url).path
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/external/members':
            data = dict(items=rows, total=len(rows))
        elif path == '/api/external/members/export-emails':
            req = route.request
            assert req.method == 'POST'
            assert req.headers['authorization'] == 'Bearer synthetic-ui-test'
            ids = req.post_data_json['ids']
            requests.append(ids)
            await asyncio.sleep(.3)
            if reject:
                await route.fulfill(status=reject, json={'detail': '模拟导出失败'})
            else:
                content = emails_xlsx([next(row['email'] for row in rows if row['id'] == mid) for mid in ids])
                await route.fulfill(content_type=XLSX_MEDIA_TYPE, body=content)
            return
        elif path.endswith('/jobs'):
            data = []
        else:
            data = {'items': [], 'total': 0}
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('download', lambda d: downloads.append(d))
        await page.route('**/api/**', api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/external-members')
        await expect(page.locator('tr[data-member]')).to_have_count(3)
        button = page.locator('#extm-export-emails')
        await expect(button).to_be_disabled()
        await page.locator('[data-member="2"] .extm-rowck').check()
        await page.locator('[data-member="3"] .extm-rowck').check()
        await expect(button).to_have_text('导出选中邮箱（2）')
        async with page.expect_download() as downloading:
            await button.click()
            await expect(button).to_be_disabled()
        download = await downloading.value
        assert download.suggested_filename == 'external-emails.xlsx'
        content = Path(await download.path()).read_bytes()
        with ZipFile(BytesIO(content)) as archive:
            sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            assert [node.text for node in sheet.findall('.//s:t', ns)] == [
                '邮箱', 'account2@example.com', 'account3@example.com']
        assert requests == [[2, 3]]
        await expect(page.locator('#extm-op')).to_have_text('已导出 2 个邮箱（Excel）')
        await expect(button).to_be_enabled()
        await page.locator('#extm-ckall').check()
        async with page.expect_download():
            await button.click()
        assert set(requests[-1]) == {1, 2, 3}
        await page.locator('#extm-ckall').uncheck()
        await expect(button).to_be_disabled()
        await page.locator('[data-member="1"] .extm-rowck').check()
        for reject, message in [(503, '模拟导出失败'), (401, '未登录,请重新登录后台')]:
            await button.click()
            await expect(page.locator('#extm-op')).to_have_text(message)
            await expect(button).to_be_enabled()
        assert len(downloads) == 2
        reject = 0
        async with page.expect_download():
            await button.click()
        await expect(button).to_have_text('导出选中邮箱（1）')
        (ROOT / '.local').mkdir(exist_ok=True)
        await page.screenshot(path=str(ROOT / '.local/external-email-export-ui.png'), full_page=True)
        await page.set_viewport_size({'width': 390, 'height': 844})
        await expect(button).to_be_visible()
        bounds = await button.bounding_box()
        assert 0 <= bounds['x'] and bounds['x'] + bounds['width'] <= 391
        assert not errors, errors
        await browser.close()
    print('PASS: Excel contents, selection, select-all, disabled/loading state, auth/errors, retry, mobile layout')


if __name__ == '__main__':
    asyncio.run(main())
