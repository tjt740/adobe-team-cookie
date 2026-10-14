"""Import drawer: focus, draft retention, submission, routing and responsive layout.

All requests use synthetic fixtures and local frontend assets.
"""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect
from external_controls import select_value as choose_option, expect_select
from mobile_workspace_ui import Fixtures

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'external-import-preview'


async def select_value(page, selector, value):
    await choose_option(page, selector, value)
    # Let the native menu exit before opening another control or dismissing its dialog.
    await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)


class ImportFixtures(Fixtures):
    fail_import = True

    async def serve(self, route):
        path = urlparse(route.request.url).path.removeprefix(self.prefix)
        if path == '/api/external/members/import':
            self.writes.append((path, route.request.post_data_json))
            await asyncio.sleep(.3)
            if self.fail_import:
                return await route.fulfill(status=503, json={'detail': '模拟导入失败，请重试'})
            return await route.fulfill(json=dict(created=1, updated=0, skipped=0, failed=0, errors=[], job_id=987))
        return await super().serve(route)


async def check(browser, prefix):
    context = await browser.new_context(viewport={'width':1440,'height':1000}, locale='zh-CN')
    fixtures, errors = ImportFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-import-drawer')")
    page = await context.new_page()
    page.set_default_timeout(10000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto('http://import.test'+prefix+'/external-members')
    await expect(page.locator('tr[data-member]')).to_have_count(54)
    drawer = page.get_by_role('dialog', name='导入外部子号', exact=True)
    await expect(drawer).not_to_be_visible()
    await expect(page.locator('#extm-import')).not_to_be_visible()
    await page.locator('#extm-open-import').click()
    await expect(drawer).to_be_visible()
    await expect(page.locator('#extm-import-close')).to_be_focused()
    await expect(drawer.get_by_text('导入格式示例', exact=True)).to_be_visible()
    await expect(drawer.locator('code')).to_have_count(3)
    await expect(page.locator('#extm-open-import')).to_have_attribute('aria-expanded','true')
    # Focus stays inside the modal, and its selects render above the modal surface.
    await page.keyboard.press('Tab')
    await page.locator('#extm-refresh').evaluate('el => el.focus()')
    assert await page.evaluate("document.activeElement.closest('#extm-import-drawer') !== null")
    await page.locator('#extm-import').fill('draft@example.com----Password')
    await select_value(page, '#extm-dup', 'overwrite')
    await select_value(page, '#extm-otp-mode', 'manual')
    await page.keyboard.press('Escape')
    await expect(drawer).not_to_be_visible()
    await expect(page.locator('#extm-open-import')).to_be_focused()
    await page.locator('#extm-open-import').click()
    await expect(page.locator('#extm-import')).to_have_value('draft@example.com----Password')
    await expect_select(page, '#extm-dup', 'overwrite')
    await expect_select(page, '#extm-otp-mode', 'manual')
    await page.locator('#extm-dup .n-base-selection').click()
    await page.keyboard.press('Escape')
    await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
    await expect(drawer).to_be_visible()
    # Failed submissions retain the draft, successful ones clear it, and feedback stays in the drawer.
    await page.locator('#extm-do-import').click()
    await expect(page.locator('#extm-do-import')).to_be_disabled()
    await expect(page.locator('#extm-import-result')).to_contain_text('模拟导入失败')
    await expect(page.locator('#extm-import')).to_have_value('draft@example.com----Password')
    fixtures.fail_import = False
    await page.locator('#extm-do-import').click()
    await expect(page.locator('#extm-import-result')).to_contain_text('登录任务 #987')
    await expect(page.locator('#extm-import')).to_have_value('')
    assert len(fixtures.writes) == 2, fixtures.writes
    assert fixtures.writes[-1][1] == dict(content='draft@example.com----Password', on_duplicate='overwrite', otp_mode='manual')
    await page.locator('#extm-do-import').click()
    await expect(page.locator('#extm-import-result')).to_contain_text('请粘贴')
    assert len(fixtures.writes) == 2
    await page.locator('#extm-import-close').click()
    await expect(page.locator('#extm-open-import')).to_be_focused()
    # Click the backdrop to dismiss; navigation also closes the top-layer modal.
    await page.locator('#extm-open-import').click()
    await expect(drawer).to_be_visible()
    await page.mouse.click(100, 150)
    await expect(drawer).not_to_be_visible()
    await page.locator('#extm-open-import').click()
    await page.evaluate("window.OKAD_NAV.navigate('/logs')")
    await expect(page.locator('#extm-embed')).not_to_be_visible()
    await expect(drawer).not_to_be_visible()
    await page.locator('#extm-nav').click()
    await expect(page.locator('#extm-open-import')).to_be_visible()
    for width, height in ((1440,1000),(390,844),(320,360)):
        await page.set_viewport_size({'width':width,'height':height})
        await page.locator('#extm-open-import').click()
        await expect(drawer).to_be_visible()
        await select_value(page, '#extm-otp-mode', 'auto')
        await page.locator('#extm-mail-config > summary').click()
        await page.locator('#extm-mail-token').fill('synthetic-token')
        await expect(page.locator('#extm-mail-save')).to_be_visible()
        geometry = await drawer.evaluate('''el => {
          const r=el.getBoundingClientRect(), body=el.querySelector('.extv-drawer-body'), footer=el.querySelector('footer').getBoundingClientRect();
          return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,footer:footer.bottom,overflow:body.scrollWidth-body.clientWidth};
        }''')
        assert geometry['left'] >= -1 and geometry['right'] <= width+1, geometry
        assert geometry['top'] >= -1 and geometry['bottom'] <= height+1, geometry
        assert geometry['footer'] <= height+1 and geometry['overflow'] <= 1, geometry
        await page.locator('#extm-mail-config > summary').click()
        await select_value(page, '#extm-otp-mode', '')
        await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
        await page.locator('.extv-drawer-body').evaluate('el => el.scrollTop=0')
        if not prefix:
            await page.screenshot(path=str(OUTPUT/f'drawer-{width}.png'), animations='disabled')
        await page.locator('#extm-import-done').click()
    await page.set_viewport_size({'width':1440,'height':1000})
    await page.evaluate("localStorage.setItem('okad-theme','dark')")
    await page.reload()
    await page.locator('#extm-open-import').click()
    color = await drawer.evaluate('el => getComputedStyle(el).backgroundColor')
    assert color != 'rgb(255, 255, 255)', color
    if not prefix:
        await page.screenshot(path=str(OUTPUT/'drawer-dark.png'), animations='disabled')
    assert not errors, errors
    assert not fixtures.escaped, fixtures.escaped
    await context.close()


async def main():
    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('DRAWER_BROWSER','chromium')).launch()
        for prefix in ('','/okad'):
            await check(browser,prefix)
        await browser.close()
    print('PASS: import drawer focus, selects, draft retention, submit/error handling, dismissal, routing, dark theme and 320–1440px layout on both deployment paths')


if __name__ == '__main__':
    asyncio.run(main())
