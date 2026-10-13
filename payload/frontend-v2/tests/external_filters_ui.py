"""Inventory/date filters with local assets and synthetic APIs; no live writes."""
import asyncio
from datetime import datetime
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

FRONT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parents[3] / '.local'


async def main():
    rows = [dict(id=i, email=f'filter{i:03d}@example.test', login_status='ok',
                 has_cookie=True, subscription_ok=True, credits_total=4000,
                 created_at='2026-10-12T00:00:00Z' if i <= 130 else '2026-10-13T00:00:00Z')
            for i in range(1, 262)]
    inventory = {row['id'] for row in rows if row['id'] % 3 == 0}
    state = dict(fail=False)
    calls, actions, errors = [], [], []

    def matches(query):
        return [row for row in rows if
                ('in_stock' not in query or (row['id'] in inventory) == (query['in_stock'] == 'true')) and
                (not query.get('imported_from') or datetime.fromisoformat(row['created_at']) >= datetime.fromisoformat(query['imported_from'])) and
                (not query.get('imported_before') or datetime.fromisoformat(row['created_at']) < datetime.fromisoformat(query['imported_before'])) and
                (not query.get('keyword') or query['keyword'] in row['email'])]

    async def serve(route):
        request, url = route.request, urlparse(route.request.url)
        path = url.path.removeprefix('/okad')
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        if not path.startswith('/api/'):
            file = FRONT / path.lstrip('/')
            if not file.is_file():
                file = FRONT / ('index-okad.html' if url.path.startswith('/okad/') else 'index.html')
            await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])
            return
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/external/members':
            calls.append(query)
            if state['fail'] and 'in_stock' in query:
                await route.fulfill(status=503, json={'detail': 'Sub2 库存暂不可用'})
                return
            selected = matches(query)
            page, size = int(query['page']), int(query['size'])
            data = dict(items=selected[(page - 1) * size:page * size], total=len(selected))
        elif path == '/api/external/members/sub2-stock':
            data = dict(ok=not state['fail'], configured=True, items={row['id']: {
                'email': row['email'], 'in_stock': row['id'] in inventory, 'account_ids': []} for row in rows})
        elif path in ('/api/external/members/export', '/api/external/members/batch-login-filter'):
            actions.append((path, request.post_data_json if request.method == 'POST' else query))
            data = dict(queued=0, message='无待重登账号') if path.endswith('filter') else []
        elif path.endswith('/jobs'):
            data = []
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            page = await browser.new_page(viewport={'width': 1440, 'height': 1000}, timezone_id='Asia/Shanghai')
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.route('**/*', serve)
            await page.add_init_script("localStorage.setItem('okad_token','synthetic-filter-test')")
            await page.goto('http://okad.test' + prefix + '/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(200)
            await page.locator('.extm-import-card').first.locator('summary').click()
            await page.locator('#extm-next').click()
            await expect(page.locator('#extm-page-info')).to_have_text('第 2 / 2 页')
            await page.locator('tr[data-member] .extm-rowck').first.check()
            await page.locator('#extm-f-stock').select_option('false')
            await expect(page.locator('#extm-total')).to_have_text('174')
            await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 1 页')
            await expect(page.locator('#extm-selc')).to_have_text('0')
            await page.locator('#extm-f-import-from').fill('2026-10-12')
            await page.locator('#extm-f-import-to').fill('2026-10-12')
            await expect(page.locator('#extm-total')).to_have_text('87')
            expected = dict(in_stock='false', imported_from='2026-10-11T16:00:00.000Z', imported_before='2026-10-12T16:00:00.000Z')
            assert all(calls[-1][key] == value for key, value in expected.items()), calls[-1]
            await page.locator('#extm-page-size').select_option('50')
            await expect(page.locator('tr[data-member]')).to_have_count(50)
            await page.locator('#extm-next').click()
            await expect(page.locator('tr[data-member]')).to_have_count(37)
            await expect(page.locator('#extm-page-info')).to_have_text('第 2 / 2 页')
            await page.locator('#extm-export').click()
            await page.locator('#extm-more-actions > summary').click()
            await page.locator('#extm-login-all').click()
            await expect(page.locator('#extm-login-all')).to_be_enabled()
            assert actions[-2][1] == expected, actions[-2]
            assert actions[-1][1] == dict(expected, in_stock=False, login_status=None, subscription_ok=None, keyword=''), actions[-1]

            # Reject backwards ranges before sending them to the API.
            await page.locator('#extm-f-import-to').fill('2026-10-11')
            assert await page.locator('#extm-f-import-to').evaluate('(node) => !node.validity.valid')
            assert all(calls[-1][key] == value for key, value in expected.items())
            await page.locator('#extm-f-import-to').fill('2026-10-12')
            await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 2 页')

            # Both installed paths and narrow layouts keep controls inside the viewport.
            for width in (1440, 390):
                await page.set_viewport_size({'width': width, 'height': 1000})
                await page.locator('#extm-f-stock').scroll_into_view_if_needed()
                for selector in ('#extm-f-stock', '#extm-f-import-from', '#extm-f-import-to', '#extm-reset-filters'):
                    box = await page.locator(selector).bounding_box()
                    assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1, (width, selector, box)
                if not prefix:
                    await page.screenshot(path=str(OUTPUT / f'external-filters-{width}.png'))
            await page.set_viewport_size({'width': 1440, 'height': 1000})
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('#extm-total')).to_have_text('261')
            await expect(page.locator('#extm-f-import-from')).to_have_value('')
            await expect(page.locator('#extm-f-stock')).to_have_value('')

            state['fail'] = True
            await page.locator('#extm-f-stock').select_option('false')
            await expect(page.locator('#extm-tbody')).to_contain_text('Sub2 库存暂不可用')
            await page.locator('#extm-refresh').click()
            await expect(page.locator('#extm-tbody')).to_contain_text('Sub2 库存暂不可用')
            state['fail'] = False
            await page.locator('#extm-refresh').click()
            await expect(page.locator('#extm-total')).to_have_text('174')
            assert not errors, errors
            await page.close()
        await browser.close()
    print('PASS: stock/date combination, local day boundaries, pagination, selection reset, action scope, invalid ranges, error recovery and desktop/mobile layout')


if __name__ == '__main__':
    asyncio.run(main())
