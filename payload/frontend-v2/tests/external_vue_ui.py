"""Naive UI integration: real menus, keyboard, theme, routing and responsive filter geometry."""
import asyncio
from pathlib import Path
from urllib.parse import urlparse
import re

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures
from external_controls import select_value, expect_select

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'external-vue-preview'


class ViewFixtures(Fixtures):
    reject_profile = False

    async def serve(self, route):
        path = urlparse(route.request.url).path.removeprefix(self.prefix)
        if path == '/api/external/members/login-profile':
            payload = route.request.post_data_json
            self.writes.append((path, payload))
            if self.reject_profile:
                return await route.fulfill(status=503, json={'detail':'模拟保存失败'})
            for row in self.rows:
                if row['id'] in payload['ids']:
                    row['profile_preference'] = payload['profile_preference']
            return await route.fulfill(json={'profile_preference':payload['profile_preference'],'message':'已保存登录配置'})
        return await super().serve(route)


async def main():
    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            context = await browser.new_context(viewport={'width':1440,'height':1100}, locale='zh-CN', timezone_id='Asia/Shanghai')
            fixtures, errors = ViewFixtures(prefix), []
            await context.route('**/*', fixtures.serve)
            await context.add_init_script("localStorage.setItem('okad_token','synthetic-vue-test')")
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto('http://vue.test'+prefix+'/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(54)
            await expect(page.locator('#extm-embed > .n-config-provider')).to_have_count(1)
            await expect(page.locator('#extm-refresh.n-button')).to_have_count(1)

            # Batch preference changes only checked accounts, and rolls back after API failure.
            for member in (1,3):
                await page.locator(f'[data-member="{member}"] .extm-rowck').check()
            await page.locator('#extm-batch-profile .n-base-selection').click()
            await page.locator('.n-base-select-option:visible').get_by_text('个人配置',exact=True).click()
            await expect(page.locator('#extm-batch-profile .n-base-selection-label')).to_have_text('个人配置')
            assert fixtures.writes[-1][1] == {'ids':[1,3],'profile_preference':'personal'}
            fixtures.reject_profile = True
            await page.locator('#extm-batch-profile .n-base-selection').click()
            await page.locator('.n-base-select-option:visible').get_by_text('组织配置优先',exact=True).click()
            await expect(page.locator('#extm-op')).to_contain_text('模拟保存失败')
            await expect(page.locator('#extm-batch-profile .n-base-selection-label')).to_have_text('个人配置')
            await page.locator('[data-member="2"] .extm-rowck').check()
            await expect(page.locator('#extm-batch-profile .n-base-selection')).to_have_class(re.compile('n-base-selection--disabled'))
            await page.locator('#extm-ckall').check()
            await page.locator('#extm-ckall').uncheck()

            # Reset also cancels a pending search; polling cannot restore the draft.
            await page.locator('#extm-f-kw').fill('pending@example.test')
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('#extm-f-kw')).to_have_value('')
            await select_value(page, '#extm-f-profile', 'personal')
            await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
            await page.locator('#extm-f-profile .n-base-selection-label').focus()
            await page.keyboard.press('Enter')
            await expect(page.locator('.n-base-select-option:visible')).to_have_count(4)
            await page.keyboard.press('Escape')
            await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)

            # Teleported menus disappear when leaving and work again when returning.
            await page.locator('#extm-f-company .n-base-selection').click()
            await page.locator('.n-layout-sider a').filter(has_text='日志管理').click()
            await expect(page.locator('#extm-embed')).not_to_be_visible()
            await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
            await page.locator('#extm-nav').click()
            await expect_select(page, '#extm-f-profile', 'personal')
            await select_value(page, '#extm-f-company', 'true')
            await expect_select(page, '#extm-f-company', 'true')
            await page.locator('#extm-reset-filters').click()

            for width in (320,390,768,1440,2560,3448):
                await page.set_viewport_size({'width':width,'height':1100})
                await page.locator('.extv-filters').scroll_into_view_if_needed()
                overflow = await page.locator('.extv-filters').evaluate('''el => {
                  const r=el.getBoundingClientRect();
                  return [...el.querySelectorAll('.n-select,.n-input,.n-input-number,.n-button')].filter(n=>{
                    const box=n.getBoundingClientRect(); return box.left<r.left-1 || box.right>r.right+1;
                  }).map(n=>n.id||n.className);
                }''')
                assert not overflow, (width, overflow)
                await page.locator('#extm-f-company .n-base-selection').click()
                await expect(page.locator('.n-base-select-option:visible')).to_have_count(3)
                await page.keyboard.press('Escape')
                await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
                if not prefix and width in (390,1440,3448):
                    await page.locator('.extv-filters').screenshot(path=str(OUTPUT/f'filters-{width}.png'))

            await page.set_viewport_size({'width':1440,'height':1100})
            await page.evaluate("localStorage.setItem('okad-theme','dark')")
            await page.reload()
            await expect(page.locator('tr[data-member]')).to_have_count(54)
            color = await page.locator('#extm-f-kw').evaluate('node => getComputedStyle(node.closest(".n-input")).getPropertyValue("--n-color")')
            assert color.strip() and color.strip() not in ('#fff','#ffffff','rgb(255, 255, 255)'), color
            await select_value(page, '#extm-f-stock', 'false')
            await expect_select(page, '#extm-f-stock', 'false')
            if not prefix:
                await page.locator('.extv-filters').screenshot(path=str(OUTPUT/'filters-dark.png'))

            # An in-app logout destroys the shell; a new login must remount the Vue panel.
            await page.evaluate("async () => { localStorage.removeItem('okad_token'); await window.OKAD_NAV.navigate('/login'); }")
            await expect(page.locator('.login-page')).to_be_visible()
            await page.evaluate("async () => { localStorage.setItem('okad_token','synthetic-vue-test'); await window.OKAD_NAV.navigate('/external-members'); }")
            await expect(page.locator('tr[data-member]')).to_have_count(54)
            await select_value(page, '#extm-f-company', 'false')
            await expect_select(page, '#extm-f-company', 'false')
            assert not errors, errors
            assert not fixtures.escaped, fixtures.escaped
            assert len(fixtures.writes) == 2, fixtures.writes
            await context.close()
        await browser.close()
    print('PASS: Vue/Naive UI components, profile save/rollback/busy guard, keyboard menus, route return/logout remount, reset, 320–3448px filters, dark theme and both deployment paths')


if __name__ == '__main__':
    asyncio.run(main())
