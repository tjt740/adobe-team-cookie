"""Pool delete UI and all-types default; synthetic records only."""
import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    rows = [dict(id=i, admin_id=0, admin_email='', email=f'pool{i}@example.com',
                 display_name='', status='registered', credits=4000, registered=i != 3,
                 is_admin=i == 3, is_imported=i != 3, has_token=True, has_cookie=True,
                 has_arp=False, created_at='2026-09-26T00:00:00Z') for i in (1, 2, 3)]
    requests, pool_types, errors = [], [], []
    reject = False

    async def route_api(route):
        nonlocal rows
        url = urlparse(route.request.url)
        if url.path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif url.path == '/api/pool':
            pool_types.append(parse_qs(url.query).get('pool_type', [''])[0])
            data = dict(items=rows, total=len(rows), page=1, size=500)
        elif url.path == '/api/pool/batch-delete':
            ids = route.request.post_data_json['ids']
            requests.append(ids)
            await asyncio.sleep(.4)
            if reject:
                await route.fulfill(status=500, json={'detail': '模拟删除失败'})
                return
            rows = [r for r in rows if r['id'] not in ids]
            data = dict(success=True, message=f'已从号池移除 {len(ids)} 条')
        elif url.path == '/api/dashboard/overview':
            count = sum(not r['is_admin'] for r in rows)
            data = {'members': {'registered': count, 'full4000': count, 'building': 0, 'zero': 0, 'cookie': count}}
        elif url.path == '/api/adobe-accounts/jobs':
            data = []
        elif url.path == '/api/sub2/pool-membership':
            data = dict(ok=True, in_sub2=[])
        else:
            data = {}
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1600, 'height': 1050})
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/api/**', route_api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/pool')
        await expect(page.locator('.n-base-selection').first).to_contain_text('全部')
        await expect(page.locator('tbody tr')).to_have_count(3)
        assert pool_types[0] == 'all'
        await page.locator('.n-base-selection').first.click()
        await page.locator('.n-base-select-option').filter(has_text='导入').click()
        await expect(page.locator('.n-base-selection').first).to_contain_text('导入')
        await page.get_by_text('总子号', exact=True).click()
        await expect(page.locator('.n-base-selection').first).to_contain_text('全部')
        assert pool_types[-1] == 'all'
        for i in (1, 3):
            await page.locator('tbody tr').filter(has_text=f'pool{i}@example.com').get_by_role('checkbox').click()
        button = page.get_by_role('button', name='批量删除', exact=True)
        await button.click()
        await expect(page.locator('.n-popconfirm')).to_contain_text('母号仅移除号池记录')
        await page.get_by_role('button', name='确认', exact=True).click()
        await expect(button).to_be_disabled()
        await expect(page.locator('tbody tr')).to_have_count(1)
        assert requests == [[1, 3]]
        # Both counters and rows refresh after successful deletion.
        overview = await page.get_by_text('总子号', exact=True).evaluate('(el)=>el.parentElement.textContent')
        assert '1' in overview, overview
        await page.reload()
        await expect(page.locator('.n-base-selection').first).to_contain_text('全部')
        await expect(page.locator('tbody tr')).to_have_count(1)
        reject = True
        await page.locator('tbody tr').get_by_role('checkbox').click()
        await button.click()
        await page.get_by_role('button', name='确认', exact=True).click()
        await expect(page.get_by_text('模拟删除失败', exact=True)).to_be_visible()
        await expect(button).to_be_enabled()
        await expect(page.locator('tbody tr').get_by_role('checkbox')).to_be_checked()
        await expect(page.locator('tbody tr')).to_have_count(1)
        await page.screenshot(path=str(Path(__file__).resolve().parents[3] / '.local/pool-delete-ui.png'), full_page=True)
        assert not errors, errors
        await browser.close()
    print('PASS: all-types default/reset, selected batch delete, counter refresh, retained selection on error')


if __name__ == '__main__':
    asyncio.run(main())
