"""Common management layout and existing forms remain usable. All API traffic mocked."""
import asyncio, os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('ADOBE_TEST_URL','http://127.0.0.1:18080');ROOT=Path(__file__).resolve().parents[3]
async def main():
    requests=[];errors=[]
    admin=dict(id=1,email='owner@example.com',is_valid=True,has_org=True,member_count=3,product_name='Adobe Firefly',remark='示例团队',refresh_token='synthetic-rt',client_id='synthetic-client')
    mail=dict(id=2,email='mail@example.com',password='synthetic-password',refresh_token='synthetic-rt',client_id='synthetic-client',mail_url='',is_used=False,remark='备用邮箱')
    overview={'admins':{'total':1,'valid':1,'type2e':0,'dead_org':0,'unchecked':0},'emails':{'total':1,'unused':1,'used':0}}
    async def api(route):
        req=route.request;url=urlparse(req.url);path=url.path;requests.append((req.method,path,parse_qs(url.query)))
        if path=='/api/auth/me':out=dict(id=1,username='admin',is_active=True,is_superuser=True)
        elif path=='/api/adobe-accounts':out=dict(items=[admin],total=1,page=1,size=20)
        elif path=='/api/emails':out=dict(items=[mail],total=1,page=1,size=20)
        elif path=='/api/dashboard/overview':out=overview
        elif path=='/api/logs':out=dict(items=[dict(id=1,time='2026-09-26 12:00:00',level='INFO',source='system',message='服务已启动')])
        elif path=='/api/sub2/config':out=dict(admin_token_set=True,base_url='http://sub2.test',platform='adobe',group_ids='2')
        elif path=='/api/sub2/accounts':out=dict(ok=True,accounts=[],total=0)
        elif path=='/api/settings':out=dict(concurrency=2,proxy_enabled=False)
        elif path.endswith('/jobs'):out=[]
        else:out=dict(items=[],total=0,ok=True)
        await route.fulfill(json=out)
    async with async_playwright() as p:
        b=await p.chromium.launch();page=await b.new_page(viewport={'width':1600,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)));await page.route('**/api/**',api)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-workspace')")
        await page.goto(BASE+'/adobe');await expect(page.locator('#adobe-workspace')).to_be_visible()
        await expect(page.get_by_text('owner@example.com',exact=True)).to_be_visible()
        await page.get_by_role('button',name='新增账号',exact=True).click()
        await expect(page.get_by_placeholder('example@hotmail.com')).to_be_visible()
        await page.get_by_role('button',name='取消',exact=True).click()
        await page.locator('tbody tr').get_by_role('checkbox').check()
        await expect(page.get_by_role('button',name='批量拉号',exact=True)).to_be_enabled()
        await page.locator('.ws-maintenance-menu summary').click()
        await expect(page.get_by_role('button',name='批量更新号池',exact=True)).to_be_visible()
        await page.locator('.ws-maintenance-menu summary').click()
        await page.locator('tbody tr').get_by_role('button',name='更多 ▾').click()
        await page.get_by_text('编辑',exact=True).click()
        await expect(page.get_by_placeholder('example@hotmail.com')).to_have_value('owner@example.com')
        await page.get_by_role('button',name='取消',exact=True).click()
        await page.screenshot(path=str(ROOT/'.local/unified-adobe.png'),full_page=True)
        await page.goto(BASE+'/email');await expect(page.locator('#email-workspace')).to_be_visible()
        await expect(page.locator('tbody')).not_to_contain_text('synthetic-password')
        await expect(page.locator('tbody')).to_contain_text('微软授权已配置')
        await page.get_by_role('button',name='查看 / 编辑',exact=True).click()
        await expect(page.get_by_placeholder('example@outlook.com')).to_have_value('mail@example.com')
        await page.get_by_role('button',name='取消',exact=True).click()
        await page.screenshot(path=str(ROOT/'.local/unified-email.png'),full_page=True)
        for width in [1024,768]:
            await page.set_viewport_size({'width':width,'height':1000})
            assert not await page.locator('#email-workspace').evaluate('e=>e.scrollWidth>e.clientWidth+2')
        await page.set_viewport_size({'width':1600,'height':1000})
        await page.goto(BASE+'/logs');await expect(page.locator('#logs-workspace')).to_be_visible()
        await page.get_by_role('button',name='详情',exact=True).click()
        await expect(page.get_by_text('日志详情',exact=True)).to_be_visible()
        await page.keyboard.press('Escape')
        await page.locator('#extm-nav').click()
        await expect(page.locator('.extm-import-card')).not_to_have_attribute('open','')
        await page.locator('.extm-import-card summary').click()
        await expect(page.locator('#extm-import')).to_be_visible()
        await page.locator('.extm-import-card summary').click()
        await page.screenshot(path=str(ROOT/'.local/unified-external.png'),full_page=True)
        await page.locator('#sub2-nav-mng').click();await expect(page.locator('.s2-overview')).to_be_visible()
        await page.screenshot(path=str(ROOT/'.local/unified-sub2.png'),full_page=True)
        await page.goto(BASE+'/settings');await expect(page.locator('#ws-settings-heading')).to_be_visible()
        await page.locator('.ws-settings-nav').get_by_role('button',name='管理员密码',exact=True).click()
        await expect(page.get_by_text('修改管理员密码',exact=True)).to_be_in_viewport()
        assert not [r for r in requests if r[0] not in ('GET','HEAD')],requests
        assert not errors,errors
        await b.close()
    print('PASS: unified account/mail/log/settings/external/Sub2 layout, preserved dialogs and menus, responsive tables, no unintended mutations')
if __name__=='__main__':asyncio.run(main())
