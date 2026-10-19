"""External-member pagination against synthetic, server-paginated API responses.

Run with payload/backend/.venv/bin/python; local assets and synthetic APIs are served by the test.
Every API request is intercepted; no account, login or production data is used.
"""
import asyncio
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from external_controls import select_value, expect_select
from playwright.async_api import async_playwright, expect
from external_controls import select_value, expect_select

ROOT = Path(__file__).resolve().parents[3]
BASE = os.environ.get('ADOBE_TEST_URL', 'http://pagination.test')
FRONT = Path(__file__).resolve().parents[1]


async def main():
    rows = [dict(id=i, email=f'account{i:04d}@example.com', login_status='ok' if i % 2 else 'never',
                 subscription_ok=i % 3 == 0, latest_job=None, created_at='2026-10-11T00:00:00')
            for i in range(1, 522)]
    calls, actions, errors = [], [], []
    state = dict(hold=False, fail=False)
    held, release, delivered = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def api(route):
        req, url = route.request, urlparse(route.request.url)
        path = url.path.removeprefix('/okad')
        if not path.startswith('/api/'):
            file=FRONT/path.lstrip('/')
            if not file.is_file():file=FRONT/'index.html'
            return await route.fulfill(path=str(file),content_type=mimetypes.guess_type(file)[0])
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        data = {}
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/external/members':
            calls.append(query)
            page, size = int(query['page']), int(query['size'])
            assert size in (50, 100, 200, 500)
            matches = [row for row in rows if
                       (not query.get('keyword') or query['keyword'] in row['email']) and
                       (not query.get('login_status') or query['login_status'] == row['login_status']) and
                       (not query.get('subscription_ok') or (query['subscription_ok'] == 'true') == row['subscription_ok'])]
            data = dict(items=matches[(page - 1) * size:page * size], total=len(matches), page=page, size=size)
            if state['hold'] and page == 2 and not query.get('login_status'):
                state['hold'] = False
                held.set()
                await release.wait()
                await route.fulfill(json=data)
                delivered.set()
                return
            if state['fail'] and page == 2:
                await route.fulfill(status=503, json={'detail': '模拟翻页失败'})
                return
        elif path == '/api/external/members/batch-delete':
            ids = req.post_data_json['ids']
            rows[:] = [row for row in rows if row['id'] not in ids]
            data = dict(success=True, message='已删除')
        elif path in ('/api/external/members/batch-login-filter', '/api/external/members/export'):
            actions.append((path, req.post_data_json if req.method == 'POST' else query))
            data = dict(queued=0, message='无待重登账号') if path.endswith('filter') else []
        elif path.endswith('/jobs'):
            data = []
        elif path == '/api/external/members/sub2-stock':
            data = dict(ok=True, configured=True, items={})
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept())
        await page.route('**/*', api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/external-members')
        table = page.locator('tr[data-member]')
        size = page.locator('#extm-page-size')
        info = page.locator('#extm-page-info')
        next_page = page.locator('#extm-next')

        async def check(count, first, label):
            await expect(table).to_have_count(count)
            if first:
                await expect(table.first).to_have_attribute('data-member', str(first))
            await expect(info).to_have_text(label)
            await expect(size).to_be_enabled()

        await check(200, 1, '第 1 / 3 页')
        await expect_select(page, '#extm-page-size', '200')
        await size.locator('.n-base-selection').click()
        assert await page.locator('.n-base-select-option:visible').all_text_contents() == ['50 条', '100 条', '200 条', '300 条', '400 条', '500 条', '1000 条']
        await page.keyboard.press('Escape')
        await expect(page.locator('#extm-prev')).to_be_disabled()
        await page.locator('#extm-ckall').check()
        await expect(page.locator('#extm-selc')).to_have_text('500')
        await next_page.click()
        await check(21, 501, '第 2 / 2 页')
        await expect(page.locator('#extm-selc')).to_have_text('0')

        # Every size starts at page one; the former 500-row cap is gone.
        await select_value(page, '#extm-page-size', '50')
        await check(50, 1, '第 1 / 11 页')
        await page.locator('#extm-last').click()
        await check(21, 501, '第 11 / 11 页')
        await expect(next_page).to_be_disabled()
        await expect(page.locator('#extm-page-summary')).to_have_text('共 521 条 · 当前 501–521 条')
        await select_value(page, '#extm-page-size', '100')
        await check(100, 1, '第 1 / 6 页')
        await page.locator('#extm-page-number').fill('6')
        await page.locator('#extm-page-number').press('Enter')
        await check(21, 501, '第 6 / 6 页')

        # Deleting a whole last page clamps back and reloads the new last page.
        await page.locator('#extm-ckall').check()
        await page.locator('#extm-batch-del').click()
        await check(100, 401, '第 5 / 5 页')
        await expect(page.locator('#extm-selc')).to_have_text('0')
        await page.locator('#extm-prev').click()
        await check(100, 301, '第 4 / 5 页')

        # Status, subscription and keyword filters reset the page, with full totals.
        await select_value(page, '#extm-f-status', 'ok')
        await check(100, 1, '第 1 / 3 页')
        await next_page.click()
        await check(100, 201, '第 2 / 3 页')
        await select_value(page, '#extm-f-sub', 'true')
        await check(83, 3, '第 1 / 1 页')
        await select_value(page, '#extm-f-status', '')
        await check(100, 3, '第 1 / 2 页')
        await next_page.click()
        await check(66, 303, '第 2 / 2 页')
        await page.locator('#extm-f-kw').fill('account003')
        await check(4, 30, '第 1 / 1 页')
        await page.locator('#extm-f-kw').fill('no-matching-email')
        await check(0, None, '第 1 / 1 页')
        await expect(page.locator('#extm-page-summary')).to_have_text('共 0 条 · 当前 0–0 条')
        await expect(next_page).to_be_disabled()
        await page.locator('#extm-f-kw').fill('')
        await check(100, 3, '第 1 / 2 页')
        await select_value(page, '#extm-f-sub', '')
        await check(100, 1, '第 1 / 5 页')

        # A slow old page must not overwrite results for newly applied filters.
        state['hold'] = True
        await next_page.click()
        await asyncio.wait_for(held.wait(), 5)
        await expect(size.locator('.n-base-selection')).to_have_class(re.compile('n-base-selection--disabled'))
        await select_value(page, '#extm-f-status', 'ok')
        await check(100, 1, '第 1 / 3 页')
        release.set()
        await asyncio.wait_for(delivered.wait(), 5)
        await check(100, 1, '第 1 / 3 页')
        await select_value(page, '#extm-f-status', '')
        await check(100, 1, '第 1 / 5 页')

        # Failed navigation clears old rows and remains recoverable via refresh.
        state['fail'] = True
        await next_page.click()
        await expect(page.locator('#extm-tbody')).to_contain_text('模拟翻页失败')
        await check(0, None, '第 2 / 5 页')
        state['fail'] = False
        await page.locator('#extm-refresh').click()
        await check(100, 1, '第 1 / 5 页')

        # Automatic refresh keeps the page, page size, selection and expanded details.
        await table.first.locator('.extm-rowck').check()
        await table.first.locator('.extm-toggle').click()
        async with page.expect_response(lambda r: '/api/external/members?' in r.url, timeout=8000):
            pass
        await check(100, 1, '第 1 / 5 页')
        await expect(page.locator('#extm-selc')).to_have_text('1')
        await expect(page.locator('[data-detail="1"]')).to_have_count(1)
        assert calls[-1]['page'] == '1' and calls[-1]['size'] == '100'
        await next_page.click()
        await check(100, 101, '第 2 / 5 页')
        await expect(page.locator('[data-detail]')).to_have_count(0)
        await expect(page.locator('#extm-selc')).to_have_text('0')

        # Full-scope actions must not receive pagination parameters.
        await page.locator('#extm-more-actions > summary').click()
        await page.locator('#extm-login-all').click()
        await expect(page.locator('#extm-op')).to_contain_text('无待重登账号')
        await page.locator('#extm-export').click()
        await expect(page.locator('#extm-op')).to_contain_text('暂无可导出的 Cookie')
        assert actions == [('/api/external/members/batch-login-filter',
                            {'login_status': None, 'subscription_ok': None, 'keyword': ''}),
                           ('/api/external/members/export', {})]

        # Table rows scroll independently; the footer reserves its own space.
        await page.locator('.extm-pagination').scroll_into_view_if_needed()
        await expect(page.locator('.extm-pagination')).to_be_in_viewport()
        await page.set_viewport_size({'width': 900, 'height': 800})
        await page.locator('.extm-pagination').scroll_into_view_if_needed()
        await expect(size).to_be_in_viewport()
        box = await page.locator('.extm-pagination').bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 901, box
        table_box = await page.locator('.extm-tw').bounding_box()
        assert table_box['y'] + table_box['height'] <= box['y'] + 1, (table_box, box)
        output = ROOT / '.local'
        output.mkdir(exist_ok=True)
        await page.screenshot(path=str(output / 'external-pagination.png'))
        assert not errors, errors
        await browser.close()
    print('external pagination UI: passed')


if __name__ == '__main__':
    asyncio.run(main())
