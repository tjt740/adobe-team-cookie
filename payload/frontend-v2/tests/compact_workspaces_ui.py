"""Shared import drawers and phone cards use the original APIs and row actions."""
import asyncio,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright,expect
from mobile_workspace_ui import Fixtures, fits, dialog_fits

OUTPUT=Path(__file__).resolve().parents[3]/'.local/compact-mobile'
class Data(Fixtures):
    fail=True
    async def serve(self,route):
        path=urlparse(route.request.url).path.removeprefix(self.prefix)
        if route.request.method=='POST' and ('import' in path):
            self.writes.append((path,route.request.post_data_json))
            await asyncio.sleep(.15)
            if self.fail:return await route.fulfill(status=503,json={'detail':'模拟导入失败，请重试'})
            return await route.fulfill(json=dict(created=1,updated=0,skipped=0,failed=0,errors=[]))
        return await super().serve(route)

async def check(browser,prefix):
    c=await browser.new_context(viewport={'width':390,'height':844},has_touch=True,reduced_motion='reduce')
    data=Data(prefix);errors=[]
    await c.route('**/*',data.serve)
    await c.add_init_script("localStorage.setItem('okad_token','synthetic-compact')")
    page=await c.new_page();page.on('pageerror',lambda e:errors.append(str(e)));base='http://compact.test'+prefix
    for route,button in [('adobe','批量导入'),('email','批量导入'),('pool','导入邮箱')]:
        await page.wait_for_load_state('networkidle')
        await page.goto(base+'/'+route,wait_until='networkidle')
        await expect(page.locator('.ws-filter-toggle')).to_be_visible()
        await expect(page.locator('.ws-filter-body')).to_be_hidden()
        await page.locator('.ws-filter-toggle').tap()
        query=page.locator('.ws-filter-body input').first
        await query.fill('draft filter')
        await page.locator('.ws-filter-toggle').tap()
        await page.locator('.ws-filter-toggle').tap();await expect(query).to_have_value('draft filter')
        await query.fill('');await page.locator('.ws-filter-toggle').tap()
        row=page.locator('.ws-card-table [data-ws-row=record]').first
        await expect(row).to_be_visible();await fits(page,'.ws-card-table')
        await row.locator('[role=checkbox]').tap()
        await expect(row.locator('[role=checkbox]')).to_have_attribute('aria-checked','true')
        await row.locator('[role=checkbox]').tap()
        actions=row.locator('[data-ws-cell=actions]');await expect(actions).to_be_visible()
        box=await actions.bounding_box();assert box['x']>=0 and box['x']+box['width']<=390
        await page.get_by_role('button',name=button,exact=True).click()
        drawer=page.locator('.ws-import-drawer');await dialog_fits(page,'.ws-import-drawer')
        await expect(drawer.get_by_text('账号内容识别',exact=True)).to_be_visible()
        content=drawer.get_by_role('textbox',name='账号内容识别')
        await content.fill('synthetic@example.test|demo')
        await drawer.get_by_role('button',name='关闭',exact=True).tap()
        await page.get_by_role('button',name=button,exact=True).click()
        await expect(content).to_have_value('synthetic@example.test|demo')
        data.fail=True
        await drawer.get_by_role('button',name='开始导入',exact=True).tap()
        await expect(drawer.locator('[role=alert]')).to_contain_text('模拟导入失败')
        await expect(content).to_have_value('synthetic@example.test|demo')
        data.fail=False
        await drawer.get_by_role('button',name='开始导入',exact=True).tap()
        await expect(drawer.locator('[role=status]')).to_contain_text('新增 1')
        await expect(content).to_have_value('')
        await page.set_viewport_size({'width':320,'height':360});await dialog_fits(page,'.ws-import-drawer')
        await drawer.get_by_role('button',name='关闭',exact=True).click(trial=True)
        await page.keyboard.press('Escape');await expect(drawer).to_have_count(0)
        await page.set_viewport_size({'width':1440,'height':1000})
        await page.get_by_role('button',name=button,exact=True).click();await dialog_fits(page,'.ws-import-drawer')
        bounds=await drawer.bounding_box();assert bounds['width']==620 and bounds['x']==820,bounds
        await drawer.get_by_role('button',name='关闭',exact=True).click()
        await page.set_viewport_size({'width':390,'height':844})
    for route,open_id,dialog_id,close_id in [('sub2','s2-open-config','s2-config-drawer','s2-config-close'),('integration','integration-open-config','integration-config-drawer','integration-close-config')]:
        await page.wait_for_load_state('networkidle')
        await page.goto(base+'/'+route,wait_until='networkidle')
        await page.locator('#'+open_id).tap();await dialog_fits(page,'#'+dialog_id)
        await expect(page.locator('#'+close_id)).to_be_focused()
        await page.keyboard.press('Escape');await expect(page.locator('#'+dialog_id)).to_be_hidden()
        await expect(page.locator('#'+open_id)).to_be_focused()
        await page.locator('#'+open_id).tap()
        await page.set_viewport_size({'width':320,'height':360});await dialog_fits(page,'#'+dialog_id)
        await page.locator('#'+close_id).tap();await page.set_viewport_size({'width':390,'height':844})
    for route in ['adobe','pool','email','logs','external-members','sub2','integration','settings']:
        await page.wait_for_load_state('networkidle')
        await page.goto(base+'/'+route,wait_until='networkidle')
        for row in await page.locator('.ws-card-table [data-ws-row=record]').all():
            box=await row.bounding_box()
            if box:assert box['x']>=0 and box['x']+box['width']<=391,(route,box)
        if not prefix:
            await page.screenshot(path=str(OUTPUT/(route+'-phone.png')))
    await page.evaluate("localStorage.setItem('okad-theme','dark')")
    await page.wait_for_load_state('networkidle')
    await page.goto(base+'/adobe',wait_until='networkidle');await page.get_by_role('button',name='批量导入',exact=True).click()
    assert await page.locator('.ws-import-drawer').evaluate("e=>getComputedStyle(e).backgroundColor")!='rgb(255, 255, 255)'
    assert len(data.writes)==6,data.writes
    assert not data.escaped and not errors,(data.escaped,errors)
    await c.close()

async def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await getattr(p,os.getenv('MOBILE_BROWSER','chromium')).launch()
        try:
            for prefix in ('','/okad'):await check(browser,prefix)
        finally:await browser.close()
    print('PASS: three imports preserve drafts and API behavior; native connection drawers; phone card selection/actions; filters; dark mode; 320px short viewports; both route bases')
if __name__=='__main__':asyncio.run(main())
