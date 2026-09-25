"""Real settings page with controlled proxy API responses; no production changes."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')
ROOT = Path(__file__).resolve().parents[3]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        state = {'available': True, 'proxy_enabled': True, 'clash_enabled': True, 'selected': '日本 S01',
                 'nodes': ['日本 S01', '新加坡 S02'], 'used_bytes': 100 * 1024**3,
                 'total_bytes': 300 * 1024**3, 'expires_at': 1810372973,
                 'updated_at': '2026-09-22T00:00:00Z'}
        posted = []
        async def api(route):
            path = urlparse(route.request.url).path
            data = {'items': [], 'total': 0, 'accounts': [], 'ok': True}
            if path == '/api/auth/me':
                data = {'id': 1, 'username': 'admin', 'is_active': True, 'is_superuser': True}
            elif path == '/api/settings':
                data = {'concurrency': 2, 'proxy_enabled': state['proxy_enabled'], 'proxy_url': ''}
            elif path.startswith('/api/settings/clash'):
                if route.request.method != 'GET':
                    posted.append((path, route.request.post_data_json))
                    await asyncio.sleep(.4)
                    if path.endswith('/enabled'):
                        state['proxy_enabled'] = state['clash_enabled'] = route.request.post_data_json['enabled']
                    if path.endswith('/node'):
                        state['selected'] = route.request.post_data_json['node']
                    if path.endswith('/subscription') and 'bad.example' in route.request.post_data_json['url']:
                        await route.fulfill(status=502, json={'detail': '订阅更新失败，已恢复原订阅和节点，请检查链接'})
                        return
                data = state
            elif path.endswith('/jobs'):
                data = []
            await route.fulfill(json=data)
        await page.route('**/api/**', api)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-clash-settings')")
        await page.goto(BASE + '/settings')
        card = page.locator('#okad-clash-settings')
        await expect(card.locator('.cl-badge')).to_have_text('已开启')
        assert await card.evaluate("e=>!!e.closest('.n-layout-content')")
        assert await card.evaluate("e=>Math.abs(e.getBoundingClientRect().width-e.nextElementSibling.getBoundingClientRect().width)<2")
        await expect(card.locator('.cl-select')).to_be_disabled()
        await card.locator('#cl-node').select_option('新加坡 S02')
        await card.locator('.cl-select').click()
        await expect(card.locator('.cl-select')).to_have_class('primary cl-select loading')
        await expect(card.locator('.cl-toggle')).to_be_disabled()
        await expect(card.locator('.cl-message')).to_contain_text('节点已切换')
        await card.locator('.cl-toggle').click()
        await card.locator('#cl-url').fill('https://bad.example/private')
        await card.locator('.cl-save').click()
        await expect(card.locator('.cl-message')).to_contain_text('已恢复原订阅')
        await expect(card.locator('.cl-edit')).to_be_visible()
        await card.locator('#cl-url').fill('https://new.example/private')
        await card.locator('.cl-save').click()
        await expect(card.locator('.cl-edit')).not_to_be_visible()
        await expect(card.locator('#cl-url')).to_have_value('')
        await card.locator('.cl-refresh').click()
        await expect(card.locator('.cl-message')).to_have_text('节点已更新')
        assert len(posted) == 4
        power = card.get_by_role('switch', name='启用 Clash 订阅代理')
        await power.click()
        await expect(power).to_be_disabled()
        await expect(power).to_have_attribute('aria-checked', 'false')
        await expect(card.locator('.cl-badge')).to_have_text('已关闭')
        await expect(card.locator('#cl-node')).to_have_value('新加坡 S02')
        await power.click()
        await expect(power).to_have_attribute('aria-checked', 'true')
        await expect(card.locator('.cl-badge')).to_have_text('已开启')
        # Long node names and narrow windows must stay inside the card.
        for width in (1440, 760, 390):
            await page.set_viewport_size({'width': width, 'height': 1000})
            assert await card.evaluate('e=>e.scrollWidth<=e.clientWidth+1'), (width, await card.evaluate('e=>({width:e.clientWidth,scroll:e.scrollWidth,items:[...e.querySelectorAll("*")].filter(x=>x.scrollWidth>x.clientWidth+1).map(x=>[x.className,x.clientWidth,x.scrollWidth])})'))
        await page.set_viewport_size({'width': 1440, 'height': 1000})
        await card.scroll_into_view_if_needed()
        await page.screenshot(path=str(ROOT / '.local/clash-settings-ui.png'))
        await page.locator('#extm-nav').click()
        await expect(card).not_to_be_visible()
        await page.locator('.n-menu-item').filter(has=page.locator('a[href="/settings"]')).click()
        await expect(card).to_be_visible()
        state['available'] = False
        await page.locator('.n-menu-item').filter(has=page.locator('a[href="/adobe"]')).click()
        await expect(card).to_have_count(0)
        await page.locator('.n-menu-item').filter(has=page.locator('a[href="/settings"]')).click()
        await expect(card.locator('.cl-badge')).to_have_text('客户端管理')
        await expect(card.locator('.cl-controls')).not_to_be_visible()
        assert not errors, errors
        await browser.close()
    print('PASS: subscription update/rollback UI, loading, node selection, responsive layout and route lifecycle')


if __name__ == '__main__':
    asyncio.run(main())
