"""Synthetic browser regression for multiple account states and stopping all tasks."""
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.async_api import async_playwright, expect

FRONT=Path(__file__).resolve().parents[1]
OUT=FRONT.parents[1]/'.local'/'account-state-preview'

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        for prefix in ('','/okad'):
            calls,errors=[],[]
            hold={'list':None,'stop':None,'fail':False}
            rows=[dict(id=i,email=f'account{i}@example.test',login_status='ok',has_cookie=True,
                       credits_total=4000,credits_available=4000,subscription_ok=True,
                       latest_job=dict(id=i,status='running' if i==1 else 'paused' if i==2 else 'done',
                                       target=1,success=0,fail=0,item_status='running' if i==1 else 'pending' if i==2 else 'done'))
                  for i in range(1,4)]
            async def serve(route):
                req,url=route.request,urlparse(route.request.url)
                path=url.path.removeprefix('/okad');query=parse_qs(url.query)
                if not path.startswith('/api/'):
                    file=FRONT/path.lstrip('/')
                    if not file.is_file():file=FRONT/('index-okad.html' if prefix else 'index.html')
                    return await route.fulfill(path=str(file),content_type=mimetypes.guess_type(file)[0])
                if path=='/api/auth/me':data=dict(id=1,username='admin',is_active=True,is_superuser=True)
                elif path=='/api/external/members':
                    calls.append((path,query)); gate=hold['list'];hold['list']=None
                    if gate:
                        gate[0].set();await gate[1].wait()
                    selected=[r for r in rows if not query.get('account_states') or
                              ('sub2_408' in query['account_states'] and r['id']==1) or
                              ('sub2_401' in query['account_states'] and r['id']==2)]
                    data=dict(items=selected,total=len(selected))
                elif path=='/api/external/members/sub2-stock':
                    data=dict(ok=True,configured=True,items={r['id']:dict(email=r['email'],in_stock=True,
                        account_ids=[r['id']],account_health=dict(state='error',codes=[408 if r['id']==1 else 401],
                        errors=[dict(code=408 if r['id']==1 else 401)])) for r in rows})
                elif path=='/api/external/members/cancel-all-jobs':
                    calls.append((path,req.post_data_json));gate=hold['stop']
                    if gate:gate[0].set();await gate[1].wait()
                    if hold['fail']:return await route.fulfill(status=503,json={'detail':'模拟终止失败'})
                    for row in rows[:2]:row['latest_job'].update(status='cancelled',item_status='cancelled')
                    data=dict(requested=2,message='已请求终止 2 个外部子号登录任务，已完成结果和日志保留')
                else:data=[] if path.endswith('/jobs') else dict(items=[],total=0)
                return await route.fulfill(json=data)
            page=await browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda e:errors.append(str(e)))
            await page.route('**/*',serve)
            await page.add_init_script("localStorage.setItem('okad_token','synthetic-status-test')")
            await page.goto('http://status.test'+prefix+'/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(3)
            await expect(page.locator('#extm-refresh')).to_have_text('搜索')
            await expect(page.locator('#extm-reset-filters')).to_have_text('重置')
            await expect(page.locator('#extm-refresh [data-okad-icon=search]')).to_be_visible()
            boxes=await page.locator('#extm-refresh,#extm-reset-filters').evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().x)')
            assert boxes[0]<boxes[1]
            gate=(asyncio.Event(),asyncio.Event());hold['list']=gate
            await page.locator('#extm-f-states .n-base-selection').click()
            await page.locator('.n-base-select-option:visible').filter(has=page.get_by_text('Sub2 408 · 请求超时',exact=True)).click()
            await asyncio.wait_for(gate[0].wait(),5)
            await expect(page.locator('#extm-results')).to_have_attribute('aria-busy','true')
            await expect(page.locator('#extm-load-overlay')).to_be_visible()
            await expect(page.locator('#extm-refresh')).to_have_attribute('aria-busy','true')
            if not prefix:
                await page.locator('#extm-filters').click(position={'x':5,'y':5})
                await page.screenshot(path=str(OUT/'loading.png'))
                await page.locator('#extm-f-states .n-base-selection').click()
            # A newer request finishes before the first one; the stale response cannot replace it.
            await page.locator('.n-base-select-option:visible').filter(has=page.get_by_text('Sub2 401 · 鉴权失败',exact=True)).click()
            await expect(page.locator('tr[data-member]')).to_have_count(2)
            await expect(page.locator('#extm-results')).to_have_attribute('aria-busy','false')
            gate[1].set()
            await page.wait_for_timeout(150)
            await expect(page.locator('tr[data-member]')).to_have_count(2)
            filtered=[q for path,q in calls if path=='/api/external/members' and q.get('account_states')]
            assert set(filtered[-1]['account_states'])=={'sub2_401','sub2_408'}
            await page.locator('#extm-filters').click(position={'x':5,'y':5})
            await expect(page.locator('#extf-state-help')).to_have_text('已选 2 个状态，满足任一即可')
            # Stop all is independent of filters, pagination, checkbox selection and visible task state.
            gate=(asyncio.Event(),asyncio.Event());hold['stop']=gate
            await page.locator('#extm-stop-all').click()
            await asyncio.wait_for(gate[0].wait(),5)
            await expect(page.locator('#extm-stop-all')).to_have_text('正在终止…')
            await expect(page.locator('#extm-stop-all')).to_be_disabled()
            gate[1].set()
            await expect(page.locator('#extm-stop-all')).to_be_enabled()
            stops=[body for path,body in calls if path.endswith('cancel-all-jobs')]
            assert stops==[None]
            await expect(page.locator('#extm-op')).to_contain_text('已请求终止 2 个')
            await expect(page.locator('[data-member="1"] .extm-status')).to_contain_text('已终止')
            hold['stop']=None;hold['fail']=True
            await page.locator('#extm-stop-all').click()
            await expect(page.locator('#extm-op')).to_contain_text('模拟终止失败')
            await expect(page.locator('#extm-stop-all')).to_be_enabled()
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('tr[data-member]')).to_have_count(3)
            assert not (calls[-1][1] or {}).get('account_states')
            for width in [2550,1440,390,320]:
                await page.set_viewport_size({'width':width,'height':1000})
                toggle=page.locator('#extm-filters .ws-filter-toggle')
                if await toggle.is_visible() and await toggle.get_attribute('aria-expanded')=='false':await toggle.click()
                for selector in ['#extm-stop-all','#extm-refresh','#extm-reset-filters','#extm-f-states']:
                    box=await page.locator(selector).bounding_box()
                    assert box and box['x']>=-1 and box['x']+box['width']<=width+1,(width,selector,box)
                alignment=await page.locator('.extf-actions').evaluate('e=>({right:e.getBoundingClientRect().right,buttons:e.querySelector(".extf-action-buttons").getBoundingClientRect().right})')
                assert abs(alignment['right']-alignment['buttons'])<=1,(width,alignment)
                if not prefix:await page.screenshot(path=str(OUT/f'states-{width}.png'))
            await page.evaluate("localStorage.setItem('okad-theme','dark')")
            await page.reload();await expect(page.locator('#extm-stop-all')).to_be_visible()
            if not prefix:await page.screenshot(path=str(OUT/'dark-320.png'))
            assert not errors,errors
            await page.close()
        await browser.close()
    print('PASS: multiple states, stale-response loading, search/reset, stop-all scope/failure, both paths, desktop/mobile/dark')

if __name__=='__main__':asyncio.run(main())
