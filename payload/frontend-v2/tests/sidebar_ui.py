"""Sidebar regression against the running local app; all API requests are mocked."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')
ROOT = Path(__file__).resolve().parents[3]


async def main():
    async def api(route):
        path = urlparse(route.request.url).path
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/settings':
            data = dict(concurrency=2)
        elif path == '/api/sub2/config':
            data = dict(base_url='', group_id=0)
        elif path == '/api/adobe-accounts/jobs':
            data = []
        else:
            data = dict(items=[], accounts=[], total=0, page=1, size=20, ok=True)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport=dict(width=1440, height=1000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.route('**/api/**', api)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-sidebar-test')")
        await page.goto(BASE + '/settings')
        await expect(page.locator('.okad-nav-custom')).to_have_count(2)
        toggle = page.locator('.n-layout-toggle-button')

        async def aligned(panel):
            await page.wait_for_timeout(400)
            result = await page.evaluate('''id => {
                const s=document.querySelector('.n-layout-sider').getBoundingClientRect();
                const h=document.querySelector('.n-layout-header').getBoundingClientRect();
                const p=document.querySelector(id).getBoundingClientRect();
                const icons=[...document.querySelectorAll('.n-layout-sider .okad-icon')].map(x=>{const r=x.getBoundingClientRect();return r.x+r.width/2});
                return {left:p.left, edge:s.right, top:p.top, bottom:h.bottom, icons, center:s.x+s.width/2};
            }''', panel)
            assert abs(result['left'] - result['edge']) <= 1, result

            assert abs(result['top'] - result['bottom']) <= 1, result
            if await page.locator('.n-layout-sider--collapsed').count():
                assert len(result['icons']) == 9, result
                assert all(abs(x-result['center']) <= 1 for x in result['icons']), result
            await expect(page.locator('.okad-current-item')).to_have_count(1)
            # The native router's old selection must not leave a second colored tile.
            colors = await page.locator('.n-menu-item:not(.okad-current-item) .n-menu-item-content').evaluate_all(
                "els => els.filter(e=>!e.matches(':hover')).map(e=>getComputedStyle(e,'::before').backgroundColor)")
            assert all(c == 'transparent' or c.endswith(', 0)') for c in colors), colors

        await page.locator('#extm-nav').click()
        await expect(page.locator('.okad-page-title')).to_have_text('外部子号')
        await expect(page).to_have_url(BASE + '/external-members')
        await page.reload()
        await expect(page.locator('.okad-page-title')).to_have_text('外部子号')
        await expect(page.locator('#extm-import')).to_be_visible()
        await expect(page).to_have_title('外部子号 - okad 管理平台')
        await aligned('#extm-embed')
        for _ in range(3):
            await toggle.click()
            await aligned('#extm-embed')
        await expect(page.locator('.n-layout-sider--collapsed')).to_have_count(1)
        await page.locator('#sub2-nav-mng').hover()
        await expect(page.locator('#okad-nav-tooltip')).to_have_text('Sub2 管理')
        await expect(page.locator('#okad-nav-tooltip')).to_be_visible()
        await page.locator('#sub2-nav-mng').focus()
        await page.locator('#sub2-nav-mng').press('Enter')
        await expect(page.locator('#extm-embed')).not_to_be_visible()
        await expect(page.locator('#sub2-panel')).to_be_visible()
        await expect(page.locator('.okad-page-title')).to_have_text('Sub2 管理')
        await aligned('#sub2-panel')
        await expect(page).to_have_url(BASE + '/sub2')
        await toggle.click()
        await aligned('#sub2-panel')
        await toggle.click()
        await aligned('#sub2-panel')
        await page.locator('#s2-close').click()
        await expect(page.locator('#sub2-panel')).not_to_be_visible()
        await expect(page.locator('.header-title')).to_be_visible()
        await expect(page.locator('.okad-current-item a')).to_have_attribute('href', '/settings')
        await page.locator('#extm-nav').focus()
        await page.locator('#extm-nav').press('Space')
        await aligned('#extm-embed')
        (ROOT / '.local').mkdir(exist_ok=True)
        await page.screenshot(path=str(ROOT / '.local/sidebar-collapsed.png'))
        # Native menu navigation must close overlays and restore the native selection.
        await page.locator('.n-menu-item').filter(has=page.locator('a[href="/adobe"]')).click()
        await expect(page).to_have_url(BASE + '/adobe')
        await expect(page.locator('#extm-embed')).not_to_be_visible()
        await expect(page.locator('.okad-current-item a')).to_have_attribute('href', '/adobe')
        await page.locator('#extm-nav').click()
        await page.go_back()
        await expect(page).to_have_url(BASE + '/adobe')
        await expect(page.locator('#extm-embed')).not_to_be_visible()
        await expect(page.locator('.okad-current-item a')).to_have_attribute('href', '/adobe')
        await page.go_back()
        await expect(page).to_have_url(BASE + '/external-members')
        await aligned('#extm-embed')
        await page.go_back()
        await expect(page).to_have_url(BASE + '/settings')
        await expect(page.locator('.okad-current-item a')).to_have_attribute('href', '/settings')
        await page.go_forward()
        await expect(page).to_have_url(BASE + '/external-members')
        await aligned('#extm-embed')
        # Real SPA layout unmount/remount (logout/login) must restore both custom entries.
        await page.evaluate("localStorage.removeItem('okad_token'); history.pushState({}, '', '/login'); dispatchEvent(new PopStateEvent('popstate'))")
        await expect(page.locator('.n-layout-sider')).to_have_count(0)
        await page.evaluate("localStorage.setItem('okad_token','synthetic-sidebar-test'); history.pushState({}, '', '/settings'); dispatchEvent(new PopStateEvent('popstate'))")
        await expect(page.locator('.okad-nav-custom')).to_have_count(2)
        await page.locator('#sub2-nav-mng').click()
        await aligned('#sub2-panel')
        await page.locator('#extm-nav').click()
        await expect(page.locator('#sub2-panel')).not_to_be_visible()
        await aligned('#extm-embed')
        for width in [1100, 1920]:
            await page.set_viewport_size(dict(width=width, height=1000))
            await aligned('#extm-embed')
        await page.screenshot(path=str(ROOT / '.local/sidebar-expanded.png'))
        # Every hit target must change the actual router path, not only a panel parameter.
        entries = [('/external-members', '#extm-embed'), ('/settings', '#ws-settings-heading'),
                   ('/dashboard', '.dash'), ('/adobe', '#adobe-workspace'), ('/pool', '#pool-workspace'),
                   ('/jobs', '#jobs-workspace'), ('/email', '#email-workspace'),
                   ('/logs', '#logs-workspace'), ('/sub2', '#sub2-panel')]
        for compact in [False, True]:
            if compact:
                await toggle.click()
                await expect(page.locator('.n-layout-sider--collapsed')).to_have_count(1)
            for hit in (['label', 'icon', 'padding'] if not compact else ['icon', 'padding']):
                for path, content in entries:
                    item = page.locator('.n-menu-item').filter(has=page.locator(f'a[href="{path}"]'))
                    if hit == 'label':
                        await item.locator('a').click()
                    elif hit == 'icon':
                        # The menu link can cover the icon; click its visible coordinates.
                        icon = item.locator('.n-menu-item-content__icon svg')
                        await expect(icon).to_be_visible()
                        bounds = await icon.bounding_box()
                        await page.mouse.click(bounds['x'] + bounds['width'] / 2, bounds['y'] + bounds['height'] / 2)
                    else:
                        await item.click(position={'x': 5, 'y': 20})
                    await expect(page).to_have_url(BASE + path)
                    await expect(page.locator('.okad-current-item a')).to_have_attribute('href', path)
                    await expect(page.locator('.okad-current-item')).to_have_count(1)
                    await expect(page.locator(content)).to_be_visible()
                    actual = await page.evaluate("async () => (await import(document.querySelector('script[type=module][src]').src)).cx.currentRoute.value.path")
                    assert actual == path, (hit, path, actual)
        # Rapid successive selections resolve to the last requested route.
        await page.evaluate('''() => {
            for (const path of ['/adobe', '/external-members', '/settings', '/sub2', '/pool'])
                document.querySelector('.n-layout-sider a[href="'+path+'"]').click();
        }''')
        await expect(page).to_have_url(BASE + '/pool')
        await expect(page.locator('#pool-workspace')).to_be_visible()
        await expect(page.locator('#sub2-panel')).not_to_be_visible()
        await expect(page.locator('#extm-embed')).not_to_be_visible()
        # Reload every menu and cold-open panel links with delayed registration.
        for path in ['/dashboard', '/adobe', '/pool', '/jobs', '/email', '/logs', '/settings']:
            await page.goto(BASE + path)
            await page.reload()
            await expect(page).to_have_url(BASE + path)
            await expect(page.locator('.okad-current-item a')).to_have_attribute('href', path)
            await expect(page.locator('.okad-current-item')).to_have_count(1)
            await expect(page.locator('body')).not_to_have_class('okad-panel-active')

        async def slow_panel(route):
            await asyncio.sleep(0.4)
            await route.continue_()

        await page.route('**/*-patch.js*', slow_panel)
        for name, label, panel, field in [('external-members', '外部子号', '#extm-embed', '#extm-import'),
                                          ('sub2', 'Sub2 管理', '#sub2-panel', '#s2-base')]:
            url = BASE + '/' + name + '?source=bookmark#saved'
            await page.goto(url)
            for _ in range(2):
                await expect(page.locator(panel)).to_be_visible()
                await expect(page.locator(field)).to_be_visible()
                await expect(page.locator('.okad-page-title')).to_have_text(label)
                await expect(page).to_have_url(url)
                await expect(page).to_have_title(label + ' - okad 管理平台')
                await expect(page.locator('.okad-current-item')).to_have_count(1)
                assert parse_qs(urlparse(page.url).query)['source'] == ['bookmark']
                assert urlparse(page.url).fragment == 'saved'
                await page.reload()
            await expect(page.locator(panel)).to_be_visible()
            if name == 'sub2':
                await page.locator('#s2-cfghd').click()
                await expect(page.locator(field)).not_to_be_visible()
                await page.reload()
                await expect(page.locator(field)).to_be_visible()
                await page.locator('#s2-close').click()
                await expect(page).to_have_url(BASE + '/dashboard')
                await page.reload()
                await expect(page.locator('.okad-current-item a')).to_have_attribute('href', '/dashboard')
                await expect(page.locator('#sub2-panel')).not_to_be_visible()
            await page.goto(BASE + '/settings?source=bookmark&panel=' + name + '#saved')
            await expect(page).to_have_url(url)
            await expect(page.locator(panel)).to_be_visible()
            await expect(page.locator('.okad-current-item a')).to_have_attribute('href', '/' + name)
        # Direct panel routes still require authentication and preserve the login destination.
        await page.unroute('**/*-patch.js*', slow_panel)
        for path in ['/external-members', '/sub2']:
            guest = await browser.new_page()
            await guest.route('**/api/**', api)
            await guest.goto(BASE + path)
            await expect(guest).to_have_url(BASE + '/login?redirect=' + path)
            await expect(guest.locator('.n-layout-sider')).to_have_count(0)
            await guest.close()
        assert not errors, errors
        print('PASS: all 9 route paths via labels/icons/padding, collapsed sidebar, rapid switches, reloads, history, legacy links and authentication; no browser errors')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
