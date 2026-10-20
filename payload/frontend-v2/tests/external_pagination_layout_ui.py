"""Keep the external-member pager outside the scrollable rows at every width.

All assets and API responses are local/synthetic; no server or live account needed.
"""
import asyncio
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from external_controls import select_value, expect_select
from playwright.async_api import async_playwright, expect

FRONT = Path(os.environ.get('OKAD_FRONTEND_DIR', Path(__file__).resolve().parents[1]))
OUTPUT = Path(__file__).resolve().parents[3] / '.local'


async def main():
    rows = [dict(id=i, email=f'pagination{i}@example.test', login_status='ok', has_cookie=True,
                 subscription_ok=True, latest_job=None, credits_available=4000, credits_total=4000,
                 created_at='2026-10-11T00:00:00') for i in range(1, 205)]

    async def serve(route):
        url = urlparse(route.request.url)
        mounted = url.path.startswith('/okad/')
        path = url.path.removeprefix('/okad')
        if path.startswith('/api/'):
            if path == '/api/auth/me':
                data = dict(id=1, username='admin', is_active=True, is_superuser=True)
            elif path == '/api/external/members':
                query = parse_qs(url.query)
                page, size = int(query.get('page', ['1'])[0]), int(query.get('size', ['500'])[0])
                data = dict(items=rows[(page - 1) * size:page * size], total=len(rows))
            elif path.endswith('/jobs'):
                data = []
            else:
                data = dict(items=[], total=0)
            await route.fulfill(json=data)
        else:
            file = FRONT / path.lstrip('/')
            if not file.is_file():
                file = FRONT / ('index-okad.html' if mounted else 'index.html')
            await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            page = await browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.route('**/*', serve)
            await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-layout-test')")
            await page.goto('http://okad.test' + prefix + '/external-members')
            await expect(page.locator('#extm-page-size')).to_have_value('500')
            await expect(page.locator('tr[data-member]')).to_have_count(204)
            await page.locator('#extm-page-size').select_option('200')
            await expect(page.locator('tr[data-member]')).to_have_count(200)
            pager, scroll = page.locator('.extm-pagination'), page.locator('.extm-tw')
            OUTPUT.mkdir(exist_ok=True)

            async def assert_layout():
                metrics = await page.evaluate('''() => {
                    const table = document.querySelector('.extm-tw');
                    const pager = document.querySelector('.extm-pagination');
                    const t = table.getBoundingClientRect(), p = pager.getBoundingClientRect();
                    return {tableBottom: t.bottom, pagerTop: p.top, tableHeight: t.height,
                            viewportHeight: innerHeight, left: p.left, right: p.right, width: innerWidth,
                            pagerOverflow: pager.scrollWidth - pager.clientWidth};
                }''')
                if metrics['tableBottom'] > metrics['pagerTop'] + 1:
                    await page.screenshot(path=str(OUTPUT / 'external-pagination-overlap.png'))
                assert metrics['tableBottom'] <= metrics['pagerTop'] + 1, metrics
                if metrics['width'] > 800:
                    assert metrics['tableHeight'] <= metrics['viewportHeight'] * .6 + 1, metrics
                assert metrics['left'] >= 0 and metrics['right'] <= metrics['width'] + 1, metrics
                assert metrics['pagerOverflow'] <= 1, metrics

            # Reproduces the reported overlap before the fix, even at page scroll zero.
            await assert_layout()
            for width, height in ((2290, 1000), (1440, 900), (900, 800), (640, 780)):
                await page.set_viewport_size({'width': width, 'height': height})
                for size in (50, 100, 200):
                    await select_value(page, '#extm-page-size', str(size))
                    await expect(page.locator('tr[data-member]')).to_have_count(size)
                    await expect(page.locator('#extm-page-size')).to_be_enabled()
                    for position in ('0', 'node.scrollHeight / 2', 'node.scrollHeight'):
                        await scroll.evaluate('(node) => { node.scrollTop = ' + position + '; node.scrollLeft = node.scrollWidth; }')
                        await pager.scroll_into_view_if_needed()
                        await assert_layout()
                    # Last-row actions remain above the footer and can receive pointer input.
                    await page.locator('tr[data-member]').last.locator('[data-row-more]').click()
                    await page.locator('#extm-row-menu [data-del]').click(trial=True)
                    await page.keyboard.press('Escape')
                    await expect(pager).to_be_in_viewport()
                    await assert_layout()
                print(f'LAYOUT_OK {prefix or "/"} {width}x{height}', flush=True)

            # Short last page and expanded details also reserve their own space.
            await page.set_viewport_size({'width': 1440, 'height': 900})
            await page.locator('#extm-next').click()
            await expect(page.locator('tr[data-member]')).to_have_count(4)
            await assert_layout()
            await scroll.evaluate('(node) => { node.scrollLeft = 0; node.scrollTop = 0; }')
            await page.locator('tr[data-member]').first.locator('.extm-toggle').click()
            await expect(page.locator('[data-detail]')).to_have_count(1)
            await page.locator('[data-detail] .extm-fold').evaluate('(node) => Promise.all(node.getAnimations().map(a => a.finished))')
            await assert_layout()
            await page.locator('#extm-first').click()
            await expect(page.locator('tr[data-member]')).to_have_count(200)
            await scroll.evaluate('(node) => { node.scrollTop = node.scrollHeight; node.scrollLeft = node.scrollWidth; }')
            await pager.scroll_into_view_if_needed()
            await page.screenshot(path=str(OUTPUT / ('external-pagination-layout' + ('-mounted' if prefix else '') + '.png')))
            await page.evaluate("document.documentElement.classList.add('dark')")
            await assert_layout()
            assert not errors, errors
            await page.close()
        await browser.close()
    print('PASS: pager never overlaps rows; all page sizes, scrolling, last-row actions, narrow/wide and mounted routes')


if __name__ == '__main__':
    asyncio.run(main())
