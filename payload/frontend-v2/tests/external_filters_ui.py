"""Combined external-member filters with local assets and synthetic APIs; no live writes."""
import asyncio
from datetime import datetime
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from external_controls import select_value, expect_select, set_import_dates

FRONT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parents[3] / '.local'


async def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    rows = [dict(id=i, email=f'filter{i:03d}@example.test', login_status='ok',
                 has_cookie=True, subscription_ok=True, credits_total=4000,
                 credits_available=None if i % 5 == 0 else (i - 1) * 25,
                 account_profile={'current_kind': 'unknown' if i % 7 == 0 else 'personal' if i % 2 else 'organization'},
                 uses_supply_mail=i % 2 == 0,
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
                (not query.get('keyword') or query['keyword'] in row['email']) and
                (not query.get('current_profile') or row['account_profile']['current_kind'] == query['current_profile']) and
                ('is_company' not in query or row['uses_supply_mail'] == (query['is_company'] == 'true')) and
                all(key not in query or (row['credits_' + query.get('credits_field', 'available')] is not None and
                    (row['credits_' + query.get('credits_field', 'available')] >= float(query[key]) if key == 'credits_min' else
                     row['credits_' + query.get('credits_field', 'available')] <= float(query[key])))
                    for key in ('credits_min', 'credits_max'))]

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
            await expect(page.locator('tr[data-member]')).to_have_count(261)
            await expect(page.locator('#extm-page-size')).to_have_value('500')
            await page.locator('#extm-page-size').select_option('200')
            await expect(page.locator('tr[data-member]')).to_have_count(200)
            await page.locator('#extm-next').click()
            await expect(page.locator('#extm-page-info')).to_have_text('第 2 / 2 页')
            await page.locator('tr[data-member] .extm-rowck').first.check()
            await select_value(page, '#extm-f-stock', 'false')
            await expect(page.locator('#extm-total')).to_have_text('174')
            await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 1 页')
            await expect(page.locator('#extm-selc')).to_have_text('0')
            await set_import_dates(page, start='2026-10-12')
            await set_import_dates(page, end='2026-10-12')
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
            await set_import_dates(page, end='2026-10-11')
            await expect(page.locator('#extm-import-date-dialog').get_by_role('alert')).to_have_text('结束日期不能早于开始日期')
            assert all(calls[-1][key] == value for key, value in expected.items())
            await set_import_dates(page, end='2026-10-12')
            await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 2 页')

            # Both installed paths and narrow layouts keep controls inside the viewport.
            for width in (1440, 390):
                await page.set_viewport_size({'width': width, 'height': 1000})
                toggle=page.locator('#extm-filters .ws-filter-toggle')
                if await toggle.is_visible() and await toggle.get_attribute('aria-expanded')=='false':await toggle.click()
                await page.locator('#extm-f-stock').scroll_into_view_if_needed()
                for selector in ('#extm-f-stock', '#extm-f-import-range', '#extm-reset-filters',
                                 '#extm-f-credits-field', '#extm-f-credits-min', '#extm-f-credits-max',
                                 '#extm-f-profile', '#extm-f-company'):
                    box = await page.locator(selector).bounding_box()
                    assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1, (width, selector, box)
                if not prefix:
                    await page.screenshot(path=str(OUTPUT / f'external-filters-{width}.png'))
            await page.set_viewport_size({'width': 1440, 'height': 1000})
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('#extm-total')).to_have_text('261')
            await expect(page.locator('#extm-f-import-from')).to_have_value('')
            await expect_select(page, '#extm-f-stock', '')

            async def set_bound(which, value):
                field = page.locator('#extm-f-credits-' + which)
                await field.fill(value)
                await field.press('Tab')

            # Zero is a real bound; missing credit results must not match it.
            await set_bound('max', '0')
            await expect(page.locator('#extm-total')).to_have_text('1')
            await expect(page.locator('tr[data-member]')).to_have_attribute('data-member', '1')
            await set_bound('max', '')
            await set_bound('min', '1000')
            await set_bound('max', '4000')
            await select_value(page, '#extm-f-profile', 'organization')
            await select_value(page, '#extm-f-company', 'true')
            await select_value(page, '#extm-f-stock', 'false')
            await set_import_dates(page, start='2026-10-12')
            await set_import_dates(page, end='2026-10-12')
            combined = dict(expected, credits_field='available', credits_min='1000', credits_max='4000',
                            current_profile='organization', is_company='true')
            expected_rows = matches(combined)
            await expect(page.locator('#extm-total')).to_have_text(str(len(expected_rows)))
            assert [int(mid) for mid in await page.locator('tr[data-member]').evaluate_all('(rows) => rows.map(row => row.dataset.member)')] == [row['id'] for row in expected_rows]
            await expect(page.locator('#extm-export')).to_have_text('导出筛选 Cookie')
            await page.locator('#extm-export').click()
            await page.locator('#extm-more-actions > summary').click()
            await expect(page.locator('#extm-login-all')).to_have_text('一键重登筛选结果')
            await page.locator('#extm-login-all').click()
            await expect(page.locator('#extm-login-all')).to_be_enabled()
            assert actions[-2][1] == combined, actions[-2]
            assert actions[-1][1] == dict(combined, in_stock=False, is_company=True, credits_min=1000, credits_max=4000,
                                         login_status=None, subscription_ok=None, keyword=''), actions[-1]

            # Invalid ranges never replace the applied filter; correcting restores it.
            await set_bound('max', '999')
            await expect(page.locator('#extf-credit-error')).to_have_text('积分最大值不能小于最小值')
            assert calls[-1]['credits_max'] == '4000'
            await set_bound('max', '4000')
            await select_value(page, '#extm-f-credits-field', 'total')
            await expect(page.locator('#extm-total')).to_have_text(str(len(matches(dict(combined, credits_field='total')))))
            await expect(page.locator('.extm-company-tag')).to_have_count(len(matches(dict(combined, credits_field='total'))))
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('#extm-total')).to_have_text('261')
            for selector in ('credits-min', 'credits-max'):
                await expect(page.locator('#extm-f-' + selector)).to_have_value('')
            for selector in ('profile', 'company'):
                await expect_select(page, '#extm-f-' + selector, '')
            await expect_select(page, '#extm-f-credits-field', 'available')
            await select_value(page, '#extm-f-company', 'false')
            await expect(page.locator('#extm-total')).to_have_text('131')
            await expect(page.locator('.extm-company-tag')).to_have_count(0)
            await select_value(page, '#extm-f-profile', 'unknown')
            await expect(page.locator('#extm-total')).to_have_text(str(len(matches(dict(is_company='false', current_profile='unknown')))))
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('#extm-total')).to_have_text('261')

            state['fail'] = True
            await select_value(page, '#extm-f-stock', 'false')
            await expect(page.locator('#extm-tbody')).to_contain_text('Sub2 库存暂不可用')
            await page.locator('#extm-refresh').click()
            await expect(page.locator('#extm-tbody')).to_contain_text('Sub2 库存暂不可用')
            state['fail'] = False
            await page.locator('#extm-refresh').click()
            await expect(page.locator('#extm-total')).to_have_text('174')
            assert not errors, errors
            await page.close()
        await browser.close()
    print('PASS: credits/profile/company/stock/date filters, zero and missing credits, pagination, action scope, reset, invalid ranges, error recovery and desktop/mobile layout')


if __name__ == '__main__':
    asyncio.run(main())
