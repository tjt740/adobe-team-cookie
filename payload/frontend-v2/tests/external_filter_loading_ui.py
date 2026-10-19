"""Hold synthetic requests to verify loading, request ordering, errors and silent polling."""
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from external_controls import select_value

FRONT = Path(__file__).resolve().parents[1]
OUTPUT = FRONT.parents[1] / '.local' / 'external-vue-preview'


def row(number):
    return dict(id=number, email=f'loading{number}@example.test', login_status='ok',
                credits_total=4000, credits_available=4000, subscription_ok=True, has_cookie=True)


class Pending:
    def __init__(self, items, status=200):
        self.items, self.status = items, status
        self.entered, self.release, self.finished = asyncio.Event(), asyncio.Event(), asyncio.Event()


async def main():
    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            plans, errors, saved = {}, [], {}

            def hold(profile='', company='', items=None, status=200, sync=''):
                pending = Pending([row(1)] if items is None else items, status)
                plans[(profile, company, sync)] = pending
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
                    query = {key: values[0] for key, values in parse_qs(url.query).items()}
                    key = (query.get('current_profile',''), query.get('is_company',''), query.get('sub2_status',''))
                    pending = plans.pop(key, None)
                    if pending:
                        pending.entered.set()
                        await pending.release.wait()
                        saved[key] = dict(items=pending.items,total=len(pending.items)) if pending.status == 200 else dict(items=[],total=0)
                        await route.fulfill(status=pending.status, json={'items':pending.items,'total':len(pending.items)} if pending.status == 200 else {'detail':'模拟筛选失败'})
                        pending.finished.set()
                        return
                    data = saved.get(key, dict(items=[row(1)], total=1))
                elif path == '/api/external/members/sub2-stock':
                    data = dict(ok=True, configured=True, items={})
                else:
                    data = dict(items=[], total=0)
                await route.fulfill(json=data)

            page = await browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.route('**/*', serve)
            await page.add_init_script("localStorage.setItem('okad_token','synthetic-loading-test')")
            await page.goto('http://loading.test'+prefix+'/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(1)
            results = page.locator('.extv-results')
            spinner = results.locator('.n-spin-body')

            async def loading(pending):
                await asyncio.wait_for(pending.entered.wait(), 5)
                await expect(results).to_have_attribute('aria-busy','true')
                await expect(spinner).to_be_visible()
                await expect(page.locator('.extv-filter-status')).to_have_text('正在更新列表…')
                await expect(page.locator('#extm-tbody')).not_to_contain_text('暂无匹配')

            async def finish(pending):
                pending.release.set()
                await asyncio.wait_for(pending.finished.wait(), 5)
                # Let fetch, Vue and the transition observe this response before checking stale requests.
                await page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')

            first = hold('personal', items=[row(2)])
            await select_value(page, '#extm-f-profile', 'personal')
            await loading(first)
            await expect(page.locator('#extm-page-go')).to_be_disabled()
            if not prefix:
                await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
                await expect(spinner).to_have_css('opacity','1')
                await page.locator('.extv-list').screenshot(path=str(OUTPUT/'filter-loading.png'))

            second = hold('personal','true',[row(3)])
            async with page.expect_event('requestfailed', predicate=lambda request:
                                        '/api/external/members?' in request.url) as cancelled:
                await select_value(page, '#extm-f-company', 'true')
            assert 'ERR_ABORTED' in (await cancelled.value).failure
            await loading(second)
            await finish(first)
            await expect(results).to_have_attribute('aria-busy','true')
            await expect(page.locator('tr[data-member]')).to_have_count(0)
            await finish(second)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(page.locator('tr[data-member]')).to_have_attribute('data-member','3')
            await expect(spinner).not_to_be_visible()

            third = hold('organization','true',[row(4)])
            await select_value(page, '#extm-f-profile', 'organization')
            await loading(third)
            latest = hold('organization','false',[row(5)])
            async with page.expect_event('requestfailed', predicate=lambda request:
                                        '/api/external/members?' in request.url) as cancelled:
                await select_value(page, '#extm-f-company', 'false')
            assert 'ERR_ABORTED' in (await cancelled.value).failure
            await loading(latest)
            await finish(latest)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(page.locator('tr[data-member]')).to_have_attribute('data-member','5')
            await finish(third)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(page.locator('tr[data-member]')).to_have_attribute('data-member','5')

            failed = hold('unknown','false',status=503)
            await select_value(page, '#extm-f-profile', 'unknown')
            await loading(failed)
            await finish(failed)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(page.locator('#extm-tbody')).to_contain_text('模拟筛选失败')

            empty = hold(items=[])
            await page.locator('#extm-reset-filters').click()
            await loading(empty)
            await finish(empty)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(page.locator('#extm-tbody')).to_contain_text('暂无匹配的外部子号')

            # Automatic polling stays quiet; explicit refresh gets the visible spinner.
            polling = hold()
            await asyncio.wait_for(polling.entered.wait(), 5)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(spinner).not_to_be_visible()
            await finish(polling)
            await expect(page.locator('tr[data-member]')).to_have_count(1)
            refresh = hold()
            await page.locator('#extm-refresh').click()
            await loading(refresh)
            await finish(refresh)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(page.locator('#extm-refresh')).to_be_enabled()
            sync = hold(sync='pending', items=[dict(row(6), sub2_status='pending')])
            await select_value(page, '#extm-f-sync', 'pending')
            await loading(sync)
            await finish(sync)
            await expect(results).to_have_attribute('aria-busy','false')
            await expect(page.locator('tr[data-member]')).to_have_attribute('data-member','6')
            await expect(page.locator('#extm-tbody')).to_contain_text('Sub2 待同步')
            if not prefix:
                await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
                await page.locator('.extv-filters').screenshot(path=str(OUTPUT/'sub2-status-filter.png'))
            assert not errors, errors
            await page.close()
        await browser.close()
    print('PASS: visible filter loading, both response orders, failure/empty recovery, reset, manual refresh and quiet polling on both paths')


if __name__ == '__main__':
    asyncio.run(main())
