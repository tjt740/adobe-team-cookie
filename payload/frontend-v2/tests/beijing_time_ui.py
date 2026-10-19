"""Beijing dates remain stable across browser zones and both mounted entrypoints."""
import asyncio
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures


class Data(Fixtures):
    async def serve(self, route):
        if urlparse(route.request.url).path.removeprefix(self.prefix) == '/api/logs':
            return await route.fulfill(json={'items': [dict(id=1, time='2026-10-18 00:02:18',
                ts=1792252938, level='INFO', source='system', message='北京时间验证')], 'total': 1})
        return await super().serve(route)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            for zone in ('UTC', 'America/Los_Angeles', 'Asia/Shanghai'):
                context = await browser.new_context(timezone_id=zone)
                data, errors = Data(prefix), []
                await context.route('**/*', data.serve)
                await context.add_init_script("localStorage.setItem('okad_token','synthetic-time-test')")
                page = await context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                await page.goto('http://beijing.test' + prefix + '/logs')
                await expect(page.locator('#logs-workspace')).to_contain_text('时间（北京时间）')
                await expect(page.locator('#logs-workspace')).to_contain_text('2026-10-18 00:02:18')
                await page.get_by_role('button', name='详情', exact=True).click()
                await expect(page.get_by_text('时间（北京时间）:', exact=True)).to_be_visible()
                values = await page.evaluate("""() => [1792252938, '2026-10-17T16:02:18Z',
                    '2026-10-17T16:02:18', '2026-10-17 16:02:18', '2026-10-18T00:02:18+08:00']
                    .map(value => window.OKAD_TIME.datetime(value))""")
                assert values == ['2026-10-18 00:02:18'] * 5, (zone, values)
                await page.goto('http://beijing.test' + prefix + '/external-members')
                await expect(page.locator('tr[data-member="1"]')).to_contain_text('2026-10-12 08:00')
                assert not errors, errors
                if prefix and zone == 'UTC':
                    await page.goto('http://beijing.test/okad/logs')
                    await expect(page.locator('#logs-workspace')).to_be_visible()
                    await page.screenshot(path=str(Path(__file__).resolve().parents[3] / '.local/beijing-release/logs.png'))
                await context.close()
        await browser.close()
    print('PASS: log table/detail and account dates use Beijing time in UTC, Los Angeles and Shanghai browsers, root and /okad')


if __name__ == '__main__':
    asyncio.run(main())
