"""Component layout, import placeholder, company tag and menu lifecycle (mock APIs)."""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures, fits
from external_controls import select_value, expect_select

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'external-filter-preview'

async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    live = os.environ.get('LIVE_UI_ORIGIN')
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in (('/okad',) if live else ('', '/okad')):
            context = await browser.new_context(viewport=dict(width=1920, height=1100), locale='zh-CN')
            fixture = Fixtures(prefix)
            fixture.rows = fixture.rows[:4]
            for i, row in enumerate(fixture.rows):
                row.update(email=f'account{i+1}@example.test', uses_supply_mail=True,
                           account_profile={'current_kind':'personal'}, sub2_status='pending')
                row.pop('otp_challenge', None)
            errors = []
            await context.route('**/api/**' if live else '**/*', fixture.serve)
            await context.add_init_script("localStorage.setItem('okad_token','synthetic-filter-layout')")
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto((live or 'http://preview.test') + prefix + '/external-members')
            await expect(page.locator('#extm-f-status .n-base-selection')).to_be_visible()
            await expect(page.locator('#extm-filters select')).to_have_count(0)
            await expect(page.locator('#extm-import-drawer')).not_to_be_visible()
            await page.locator('#extm-open-import').click()
            await expect(page.locator('#extm-import-label')).to_have_text('账号内容识别')
            await expect(page.locator('#extm-import-examples-title')).to_have_text('导入格式示例')
            await page.locator('#extm-import-done').click()
            await expect(page.locator('#extm-embed')).not_to_contain_text('操作人')
            await expect(page.locator('.extm-t > thead th')).to_have_count(11)
            color = await page.locator('.extm-company-tag').first.evaluate('(n)=>{const s=getComputedStyle(n);return [s.color,s.backgroundColor,s.borderRadius]}')
            assert color == ['rgb(24, 160, 88)', 'rgb(232, 247, 240)', '4px'], color
            for width in (3440, 1920, 1440, 768, 390, 320):
                await page.set_viewport_size(dict(width=width, height=1100))
                await fits(page, '#extm-filters')
                for selector in ('.extf-field', '.extf-range'):
                    for node in await page.locator(selector).all():
                        box = await node.bounding_box()
                        assert box['x'] >= 0 and box['x']+box['width'] <= width+1, (width, selector, box)
                await page.locator('#extm-embed').evaluate('(n)=>n.scrollTop=0')
                if not prefix or live:
                    await page.screenshot(path=str(OUTPUT / f'{"live" if live else "local"}-{width}.png'))
            await page.set_viewport_size(dict(width=1440,height=1100))
            # A pending keyword update cannot reapply old values after reset.
            await page.locator('#extm-f-kw').fill('account')
            await page.locator('#extm-reset-filters').click()
            await page.wait_for_timeout(350)
            await expect(page.locator('#extm-f-kw')).to_have_value('')
            await select_value(page,'#extm-f-company','true')
            await page.locator('#extm-f-status .n-base-selection').click()
            await expect(page.locator('.n-base-select-option:visible').first).to_be_visible()
            await page.locator('#extm-nav').evaluate("()=>{history.pushState({},'',location.pathname.replace('external-members','dashboard'));window.dispatchEvent(new PopStateEvent('popstate'))}")
            await expect(page.locator('#extm-embed')).not_to_be_visible()
            await expect(page.locator('.n-base-select-option:visible')).to_have_count(0)
            await page.locator('#extm-nav').click()
            await expect_select(page,'#extm-f-company','true')
            await page.evaluate("localStorage.setItem('okad-theme','dark')")
            await page.reload()
            await expect(page.locator('#extm-f-status .n-base-selection')).to_be_visible()
            await expect(page.locator('html')).to_have_class('dark')
            background = await page.locator('#extm-f-kw').evaluate('(n)=>getComputedStyle(n.closest(".n-input")).backgroundColor')
            assert background != 'rgb(255, 255, 255)', background
            await page.locator('#extm-embed').evaluate('(n)=>n.scrollTop=0')
            await page.screenshot(path=str(OUTPUT / 'dark.png'))
            assert not errors and not fixture.escaped, (errors,fixture.escaped)
            await context.close()
        await browser.close()
    print('PASS: Naive controls, placeholder, pale green company tag, responsive widths, reset and route menu lifecycle')

if __name__ == '__main__':
    asyncio.run(main())
