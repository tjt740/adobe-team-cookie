"""Check toolbar alignment, touch targets and menu bounds with synthetic accounts."""
import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'toolbar-nowrap'
CONTROLS = ['#extm-batch-profile .n-base-selection', '#extm-batch-login', '#extm-batch-del',
            '#extm-export', '#extm-export-emails', '#extm-sub2-push', '#extm-more-actions>summary']


async def geometry(page, width):
    result = await page.locator('.extm-batch-row').evaluate('''(el, selectors) => {
      const rect = node => {
        const r=node.getBoundingClientRect();
        return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};
      };
      return {card:rect(el.closest('.extv-list')),row:rect(el),
        controls:selectors.map(selector=>({selector,...rect(el.querySelector(selector))})),
        overflow:el.scrollWidth-el.clientWidth,
        selected:rect(el.querySelector('.selc'))};
    }''', CONTROLS)
    boxes = result['controls']
    assert max(b['bottom'] for b in boxes) - min(b['bottom'] for b in boxes) <= 1, (width, boxes)
    assert abs(result['selected']['bottom'] - boxes[0]['bottom']) <= 1
    assert result['row']['height'] <= (76 if width <= 800 else 72), (width, result)
    for i, box in enumerate(boxes):
        assert box['width'] >= 70, (width, box)
        if width <= 800:
            assert box['height'] >= 44, (width, box)
        for other in boxes[i+1:]:
            assert min(box['right'], other['right']) - max(box['x'], other['x']) <= 1, (width, box, other)
    # Desktop keeps all actions visible; small screens scroll only the toolbar.
    if width >= 1440:
        assert result['overflow'] <= 1, (width, result)
    assert await page.locator('#extm-embed').evaluate('el=>el.scrollWidth<=el.clientWidth+1'), width
    for selector in CONTROLS:
        await page.locator(selector).evaluate("el=>el.scrollIntoView({block:'nearest',inline:'nearest'})")
        box=await page.locator(selector).bounding_box()
        assert box['x'] >= 0 and box['x']+box['width'] <= width+1, (width, selector, box)
    await page.locator('.extm-batch-row').evaluate('el=>el.scrollLeft=0')



async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    engine = os.environ.get('TOOLBAR_BROWSER', 'chromium')
    async with async_playwright() as p:
        browser = await getattr(p, engine).launch()
        for prefix in ('', '/okad'):
            context = await browser.new_context(viewport={'width':1920,'height':1000}, has_touch=True,
                                                locale='zh-CN', timezone_id='Asia/Shanghai')
            fixtures, errors = Fixtures(prefix), []
            fixtures.rows=[dict(fixtures.member,id=i,email=f'toolbar{i}@example.test',
                                profile_preference='personal',sub2_status='syncing') for i in range(1,201)]
            await context.route('**/*', fixtures.serve)
            await context.add_init_script("localStorage.setItem('okad_token','synthetic-toolbar-test')")
            page = await context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            await page.goto('http://toolbar.test' + prefix + '/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(200)
            await expect(page.locator('#extm-batch-login')).to_be_disabled()
            await page.locator('#extm-ckall').check()
            await expect(page.locator('#extm-selc')).to_have_text('200')
            await expect(page.locator('#extm-sub2-push')).to_contain_text('Sub2 同步中…')
            for width in (1920,1636,1440,1280,1100,900,800,768,640,600,430,390,375,320):
                await page.set_viewport_size({'width':width,'height':1000})
                await page.locator('.extm-batch-row').scroll_into_view_if_needed()
                # Wait for the existing sidebar transition before measuring panel width.
                await expect(page.locator('#extm-embed')).to_be_visible()
                await page.locator('.extm-batch-row').evaluate('''el => new Promise(resolve =>
                  requestAnimationFrame(() => requestAnimationFrame(resolve)))''')
                await geometry(page, width)
                await expect(page.locator('#extm-batch-login')).to_be_enabled()
                if not prefix and width in (1920,1636,1440,390,320):
                    await page.locator('.extm-batch-row').screenshot(path=str(OUTPUT/f'toolbar-{engine}-{width}.png'))
                await page.locator('#extm-more-actions>summary').evaluate("el=>el.scrollIntoView({block:'nearest',inline:'nearest'})")
                await page.locator('#extm-more-actions>summary').click()
                menu = page.locator('#extm-more-actions>div')
                await expect(menu).to_be_visible()
                await page.locator('#extm-login-all').click(trial=True)
                box = await menu.bounding_box()
                assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1, (width, box)
                await page.keyboard.press('Escape')
                await expect(menu).not_to_be_visible()

            # Selection enables the same controls without moving or resizing them.
            await page.locator('#extm-ckall').uncheck()
            await page.locator('[data-member="1"] .extm-rowck').check()
            await expect(page.locator('#extm-selc')).to_have_text('1')
            await expect(page.locator('#extm-batch-login')).to_be_enabled()
            await page.locator('.extm-batch-row').scroll_into_view_if_needed()
            await geometry(page, 320)
            await page.locator('#extm-batch-profile .n-base-selection').click()
            await expect(page.locator('.n-base-select-option:visible')).to_have_count(4)
            menu = page.locator('.n-base-select-menu:visible')
            box = await menu.bounding_box()
            assert box['x'] >= 0 and box['x'] + box['width'] <= 321, box
            await page.keyboard.press('Escape')

            # Returning to desktop and switching to dark theme preserve alignment.
            await page.set_viewport_size({'width':1920,'height':1000})
            await page.locator('.extm-batch-row').scroll_into_view_if_needed()
            await page.locator('.n-layout-sider').evaluate('(el) => Promise.all(el.getAnimations().map(a=>a.finished.catch(()=>{})))')
            await geometry(page, 1920)
            await page.evaluate("localStorage.setItem('okad-theme','dark')")
            await page.reload()
            await expect(page.locator('tr[data-member]')).to_have_count(200)
            await page.locator('.extm-batch-row').scroll_into_view_if_needed()
            await page.locator('#extm-ckall').check()
            await geometry(page, 1920)
            if not prefix:
                await page.locator('.extm-batch-row').screenshot(path=str(OUTPUT/f'toolbar-{engine}-dark.png'))
            assert not errors, errors
            assert not fixtures.escaped and not fixtures.writes
            await context.close()
        await browser.close()
    print(f'PASS: {engine} single-row toolbar, 200 selected/syncing accounts, 320–1920px layouts, 44px mobile controls, menu bounds, selected/disabled states and dark theme on both paths')


if __name__ == '__main__':
    asyncio.run(main())
