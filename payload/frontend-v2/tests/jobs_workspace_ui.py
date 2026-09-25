"""Task purposes, provenance, history deep-links and controls; synthetic requests only."""
import asyncio, os
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright, expect
BASE=os.environ.get('ADOBE_TEST_URL','http://127.0.0.1:18080')
ROOT=Path(__file__).resolve().parents[3]

def job(i,t,status='done',email=None,success=1,fail=0):
    return dict(id=i,type=t,status=status,target=2,success=success,fail=fail,created_at=1790370000,finished_at=None if status=='running' else 1790370080,
                logs=['10:00:00 开始处理','10:00:01 [mail@example.com] 登录成功','10:00:05 [failed@example.com] 验证码超时，登录失败'],log_total=3,
                trace=dict(operator='操作员甲',source=dict(label='外部子号' if t=='external_login' else '号池管理',path='external' if t=='external_login' else '/pool',action='批量登录',recorded=True),accounts=[dict(id=1,email=email or 'mail@example.com',kind='external' if t=='external_login' else 'pool'),dict(id=2,email='failed@example.com',kind='pool')]),
                extra=dict(items=[dict(id=1,email=email or 'mail@example.com',status='done',message='登录成功'),dict(id=2,email='failed@example.com',status='running' if status=='running' else 'failed',message='正在登录' if status=='running' else '验证码超时')]),result=None,error='')

async def main():
    data={101:job(101,'external_login','running',email='running@example.com'),100:job(100,'pool_cookie_sub2',success=2),99:job(99,'pool_login',fail=1),98:job(98,'admin_login','error'),88:job(88,'pool_login')}
    data[100]['result']={'pushed':1,'existing':1}
    data[100]['trace']['destination']={'url':'http://sub2.test/api/v1','group_ids':[2]}
    data[100]['extra']['items'][1].update(status='existing',message='已在库，跳过')
    data[99]['result']={'still_no_token':1};data[99]['trace']['retry_from_job']=88
    data[98]['trace']={};data[98]['extra']={};data[98]['error']='缺少组织管理权限'
    calls=[];errors=[];reject_delete=True
    async def api(route):
        nonlocal reject_delete
        req=route.request;path=urlparse(req.url).path
        if path=='/api/auth/me':out=dict(id=1,username='admin',is_active=True,is_superuser=True)
        elif path=='/api/adobe-accounts/jobs':out=list(data.values())
        elif path=='/api/adobe-accounts/jobs/batch-delete':
            calls.append(('delete',req.post_data_json))
            if reject_delete:
                await route.fulfill(status=500,json={'detail':'删除失败测试'});return
            for i in req.post_data_json['ids']:data.pop(i,None)
            out={'success':True}
        elif path=='/api/pool/batch-login-retry/99':
            calls.append(('retry',99));data[102]=job(102,'pool_login','running');out=data[102]
        elif path.startswith('/api/adobe-accounts/jobs/'):
            tail=path.split('/api/adobe-accounts/jobs/')[1].split('/');i=int(tail[0])
            if i not in data:
                await route.fulfill(status=404,json={'detail':'任务不存在'});return
            if len(tail)>1:
                action=tail[1];calls.append((action,i))
                if action=='pause':data[i]['status']='paused'
                if action=='resume':data[i]['status']='running'
                if action=='cancel':data[i]['status']='cancelled';data[i]['finished_at']=1790370080
                if action=='clear-logs':data[i]['logs']=[];data[i]['log_total']=0
                out={'success':True}
            else:out=data[i]
        else:out=dict(items=[],total=0,ok=True)
        await route.fulfill(json=out)
    async with async_playwright() as p:
        browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1600,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.route('**/api/**',api);await page.add_init_script("localStorage.setItem('okad_token','synthetic-jobs')")
        await page.goto(BASE+'/jobs');await expect(page.locator('.task-card')).to_have_count(5)
        await expect(page.locator('[data-job-id="99"]')).to_contain_text('仍有账号未完成')
        await expect(page.locator('[data-job-id="100"]')).to_contain_text('新导入 1 · 已在库 1')
        await page.get_by_placeholder('任务编号、邮箱或操作者').fill('running@example.com')
        await expect(page.locator('.task-card')).to_have_count(1)
        await page.get_by_role('button',name='重置',exact=True).click()
        await page.locator('.task-stats button').nth(2).click();await expect(page.locator('.task-card')).to_have_count(2)
        await page.get_by_role('button',name='重置',exact=True).click()
        await page.screenshot(path=str(ROOT/'.local/jobs-workspace-board.png'),full_page=True)
        await page.locator('[data-job-id="100"]').get_by_role('button',name='查看详情 →').click()
        await expect(page).to_have_url(BASE+'/jobs?id=100')
        await expect(page.locator('.task-provenance')).to_contain_text('操作员甲')
        await expect(page.get_by_text('http://sub2.test/api/v1',exact=True)).to_be_visible()
        await expect(page.locator('.task-account-row')).to_have_count(2)
        await page.locator('.task-account-row').last.get_by_role('button',name='执行记录',exact=True).click()
        await expect(page.locator('.task-timeline li')).to_have_count(1)
        await expect(page.locator('.task-timeline')).to_contain_text('验证码超时')
        await page.get_by_role('tab',name='账号结果').click()
        await page.screenshot(path=str(ROOT/'.local/jobs-workspace-detail.png'),full_page=True)
        await page.goto(BASE+'/jobs?id=101')
        await page.get_by_role('button',name='暂停任务',exact=True).click()
        await expect(page.get_by_role('button',name='继续任务',exact=True)).to_be_visible()
        await page.get_by_role('button',name='继续任务',exact=True).click()
        await expect(page.get_by_role('button',name='暂停任务',exact=True)).to_be_visible()
        await page.get_by_role('button',name='终止任务',exact=True).click()
        await page.get_by_role('button',name='确认',exact=True).click()
        await expect(page.locator('.task-outcome')).to_contain_text('已终止')
        assert ('pause',101) in calls and ('resume',101) in calls and ('cancel',101) in calls
        await page.goto(BASE+'/jobs?id=99')
        await page.get_by_role('button',name='来自任务 #88',exact=True).click()
        await expect(page).to_have_url(BASE+'/jobs?id=88')
        await page.go_back();await page.get_by_role('button',name='重试未完成账号',exact=True).click()
        await expect(page).to_have_url(BASE+'/jobs?id=102')
        assert ('retry',99) in calls
        await page.goto(BASE+'/jobs?id=98')
        await expect(page.locator('.task-provenance')).to_contain_text('历史任务未记录')
        for width in [1024,768]:
            await page.set_viewport_size({'width':width,'height':1100})
            assert not await page.locator('#jobs-workspace').evaluate('e=>e.scrollWidth>e.clientWidth+2')
        await page.goto(BASE+'/jobs?id=999')
        await expect(page.get_by_role('alert')).to_contain_text('任务不存在')
        await page.get_by_role('button',name='← 返回任务列表',exact=True).click()
        await page.get_by_role('checkbox',name='选择任务 #98',exact=True).check()
        await page.get_by_role('button',name='删除选中',exact=True).click();await page.get_by_role('button',name='确认',exact=True).click()
        await expect(page.get_by_text('删除失败测试',exact=True)).to_be_visible()
        await expect(page.get_by_role('checkbox',name='选择任务 #98',exact=True)).to_be_checked()
        reject_delete=False
        await page.get_by_role('button',name='确认',exact=True).click()
        await expect(page.locator('[data-job-id="98"]')).to_have_count(0)
        assert not errors,errors
        await browser.close()
    print('PASS: task summaries, filters, account results, provenance, historical gaps, deep links, retry, controls, deletion errors and responsive layout')

if __name__=='__main__':asyncio.run(main())
