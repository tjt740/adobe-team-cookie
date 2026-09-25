"""Exercise settings patches when the SPA loads slowly; API requests are mocked."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')
ROOT = Path(__file__).resolve().parents[3]
CARDS = ['okad-local-pool-settings', 'okad-external-apikey', 'okad-captcha-settings']

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror', lambda error: errors.append(str(error)))
        async def api(route):
            path=urlparse(route.request.url).path
            data={'items':[], 'total':0, 'accounts':[], 'ok':True}
            if path == '/api/auth/me':
                data={'id':1,'username':'admin','is_active':True,'is_superuser':True}
            elif path == '/api/settings':
                data={'concurrency':2,'proxy_enabled':False,'proxy_url':''}
            elif path.endswith('/jobs'):
                data=[]
            await route.fulfill(json=data)
        async def delay_app(route):
            await asyncio.sleep(.8)
            await route.continue_()
        await page.route('**/api/**',api)
        await page.route('**/assets/index-CrrzYg-U.js',delay_app)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-settings-layout')")
        await page.goto(BASE+'/settings')
        for cid in CARDS:
            await expect(page.locator('#'+cid)).to_have_count(1)
            assert await page.locator('#'+cid).evaluate("e=>!!e.closest('.n-layout-content')"), cid+' mounted outside content'
        assert await page.evaluate('document.documentElement.scrollHeight <= innerHeight+1'), 'settings leaked into document scroll'
        # Opening either custom page must hide settings and prevent scrolling the shell.
        for nav, panel in [('#extm-nav','#extm-embed'),('#sub2-nav-mng','#sub2-panel')]:
            await page.locator(nav).click()
            await expect(page.locator(panel)).to_be_visible()
            for cid in CARDS:
                await expect(page.locator('#'+cid)).not_to_be_visible()
            await page.mouse.move(900,600)
            await page.mouse.wheel(0,1600)
            await page.wait_for_timeout(250)
            assert await page.evaluate('scrollY===0')
            assert await page.locator('.n-layout-sider').evaluate('e=>Math.abs(e.getBoundingClientRect().top)<1')
            await page.locator('.n-menu-item').filter(has=page.locator('a[href="/settings"]')).click()
            for cid in CARDS:
                await expect(page.locator('#'+cid)).to_be_visible()
        # Native navigation removes cards; returning mounts one copy inside settings.
        await page.locator('.n-menu-item').filter(has=page.locator('a[href="/adobe"]')).click()
        for cid in CARDS:
            await expect(page.locator('#'+cid)).to_have_count(0)
        await page.locator('.n-menu-item').filter(has=page.locator('a[href="/settings"]')).click()
        for cid in CARDS:
            await expect(page.locator('.n-layout-content #'+cid)).to_have_count(1)
        await page.locator('#extm-nav').click()
        await page.screenshot(path=str(ROOT/'.local/settings-overlay-fixed.png'))
        assert not errors,errors
        await browser.close()
    print('PASS: delayed SPA startup, settings card containment, overlay isolation, scrolling and route remount')

if __name__=='__main__':
    asyncio.run(main())
