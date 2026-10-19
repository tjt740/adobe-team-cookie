"""Merged Vue workspace retains deployed multi-state filters and stop-all controls."""
import asyncio
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures


class Data(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.calls, self.stops, self.fail_stop = [], 0, False

    async def serve(self, route):
        path = urlparse(route.request.url).path.removeprefix(self.prefix)
        if path == '/api/external/members':
            query = parse_qs(urlparse(route.request.url).query)
            self.calls.append(query)
            selected = self.rows[:2] if query.get('account_states') else self.rows
            return await route.fulfill(json=dict(items=selected, total=len(selected)))
        if path == '/api/external/members/cancel-all-jobs':
            self.stops += 1
            assert route.request.post_data is None
            if self.fail_stop:
                return await route.fulfill(status=503, json={'detail':'模拟终止失败'})
            return await route.fulfill(json={'requested':2, 'message':'已请求终止 2 个外部子号登录任务'})
        return await super().serve(route)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            data, errors = Data(prefix), []
            page = await browser.new_page(viewport={'width':1440, 'height':1100})
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.route('**/*', data.serve)
            await page.add_init_script("localStorage.setItem('okad_token','synthetic-merge-test')")
            await page.goto('http://merge.test'+prefix+'/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(54)
            await page.locator('#extm-f-states .n-base-selection').click()
            for label in ['Sub2 408 · 请求超时', 'Sub2 401 · 鉴权失败']:
                await page.locator('.n-base-select-option:visible').filter(has=page.get_by_text(label, exact=True)).click()
            await page.keyboard.press('Escape')
            await expect(page.locator('tr[data-member]')).to_have_count(2)
            assert set(data.calls[-1]['account_states']) == {'sub2_408', 'sub2_401'}
            await page.locator('#extm-stop-all').click()
            await expect(page.locator('#extm-op')).to_contain_text('已请求终止 2 个')
            await expect(page.locator('#extm-stop-all')).to_be_enabled()
            assert data.stops == 1
            data.fail_stop = True
            await page.locator('#extm-stop-all').click()
            await expect(page.locator('#extm-op')).to_contain_text('模拟终止失败')
            await expect(page.locator('#extm-stop-all')).to_be_enabled()
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('tr[data-member]')).to_have_count(54)
            assert 'account_states' not in data.calls[-1]
            for width in (390, 320):
                await page.set_viewport_size({'width':width, 'height':900})
                for selector in ('#extm-stop-all', '#extm-f-states'):
                    box = await page.locator(selector).bounding_box()
                    assert box and box['x'] >= 0 and box['x'] + box['width'] <= width + 1, (selector, box)
            assert not errors, errors
            await page.close()
        await browser.close()
    print('PASS: merged account-state OR filters, reset, stop-all success/failure, mobile controls and both route bases')


if __name__ == '__main__':
    asyncio.run(main())
