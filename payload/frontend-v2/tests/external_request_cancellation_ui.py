"""Cancel superseded list requests and distinguish them from real timeouts."""
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from external_controls import select_value

FRONT = Path(__file__).resolve().parents[1]


class Pending:
    def __init__(self, number):
        self.number = number
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.finished = asyncio.Event()


def row(number):
    return dict(id=number, email=f'request{number}@example.test', login_status='ok',
                has_cookie=True, subscription_ok=True, credits_total=4000)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            plans, errors = {}, []

            def hold(profile, company, number):
                pending = Pending(number)
                plans[(profile, company)] = pending
                return pending

            async def serve(route):
                url = urlparse(route.request.url)
                path = url.path.removeprefix(prefix)
                if not path.startswith('/api/'):
                    file = FRONT / path.lstrip('/')
                    if not file.is_file():
                        file = FRONT / ('index-okad.html' if prefix else 'index.html')
                    return await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])
                if path == '/api/auth/me':
                    data = dict(id=1, username='admin', is_active=True, is_superuser=True)
                elif path == '/api/external/members':
                    query = parse_qs(url.query)
                    pending = plans.pop((query.get('current_profile', [''])[0],
                                         query.get('is_company', [''])[0]), None)
                    if pending:
                        pending.entered.set()
                        await pending.release.wait()
                        await route.fulfill(json=dict(items=[row(pending.number)], total=1))
                        pending.finished.set()
                        return
                    data = dict(items=[row(1)], total=1)
                elif path == '/api/external/members/sub2-stock':
                    data = dict(ok=True, configured=True, items={})
                else:
                    data = dict(items=[], total=0)
                await route.fulfill(json=data)

            page = await browser.new_page(viewport={'width':1440, 'height':1000})
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.route('**/*', serve)
            await page.add_init_script("localStorage.setItem('okad_token','synthetic-cancellation-test')")
            await page.goto('http://request.test' + prefix + '/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(1)
            results = page.locator('#extm-results')

            first = hold('personal', '', 2)
            await select_value(page, '#extm-f-profile', 'personal')
            await asyncio.wait_for(first.entered.wait(), 5)
            await expect(results).to_have_attribute('aria-busy', 'true')
            second = hold('personal', 'true', 3)
            async with page.expect_event('requestfailed', predicate=lambda request:
                                         urlparse(request.url).path == prefix + '/api/external/members') as failed:
                await select_value(page, '#extm-f-company', 'true')
            assert 'ERR_ABORTED' in (await failed.value).failure
            await asyncio.wait_for(second.entered.wait(), 5)
            await expect(results).to_have_attribute('aria-busy', 'true')
            first.release.set()
            await asyncio.wait_for(first.finished.wait(), 5)
            await expect(results).to_have_attribute('aria-busy', 'true')
            second.release.set()
            await asyncio.wait_for(second.finished.wait(), 5)
            await expect(page.locator('tr[data-member]')).to_have_attribute('data-member', '3')
            await expect(results).to_have_attribute('aria-busy', 'false')
            await expect(page.locator('#extm-tbody')).not_to_contain_text('请求超时')

            # Exercise the real timeout handler without waiting 30 seconds.
            await page.evaluate('''() => {
              window.originalRequestTimer = window.setTimeout;
              window.setTimeout = function (fn, ms, ...args) {
                return window.originalRequestTimer(fn, ms === 30000 ? 100 : ms, ...args);
              };
            }''')
            timed_out = hold('organization', 'true', 4)
            await select_value(page, '#extm-f-profile', 'organization')
            await asyncio.wait_for(timed_out.entered.wait(), 5)
            await expect(page.locator('#extm-tbody')).to_contain_text('请求超时(30s)')
            await expect(results).to_have_attribute('aria-busy', 'false')
            await page.evaluate('window.setTimeout = window.originalRequestTimer')
            timed_out.release.set()
            await asyncio.wait_for(timed_out.finished.wait(), 5)
            await expect(page.locator('#extm-tbody')).to_contain_text('请求超时(30s)')

            # A new filter can recover after the timed-out request.
            recovered = hold('unknown', 'true', 5)
            await select_value(page, '#extm-f-profile', 'unknown')
            await asyncio.wait_for(recovered.entered.wait(), 5)
            recovered.release.set()
            await asyncio.wait_for(recovered.finished.wait(), 5)
            await expect(page.locator('tr[data-member]')).to_have_attribute('data-member', '5')
            assert not errors, errors
            await page.close()
        await browser.close()
    print('PASS: old request aborted, latest results preserved, timeout distinguished, recovery; root and /okad')


if __name__ == '__main__':
    asyncio.run(main())
