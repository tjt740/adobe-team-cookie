"""Second-precision time controls and global ordering, with synthetic APIs only."""
import asyncio
import mimetypes
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.async_api import async_playwright, expect

FRONT = Path(os.environ.get('FILTER_FRONT', str(Path(__file__).resolve().parents[1])))
OUT = Path(__file__).resolve().parents[3] / '.local' / 'external-time-sort-preview'

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('FILTER_BROWSER', 'chromium')).launch()
        for prefix in ('', '/okad'):
            for width in (1440, 390):
                calls, actions, errors = [], [], []
                imported, logged = [3, 1, 2, 2.999999, 2, 4], [None, 0, 1, 1.999999, 1, 2]
                def stamp(base, offset):
                    return (base+timedelta(seconds=offset)).isoformat() if offset is not None else None
                rows = [dict(id=i+1, email=f'time{i}@example.test', login_status='ok' if logged[i] is not None else 'never',
                             has_cookie=True, created_at=stamp(datetime(2026,10,29,4,10,tzinfo=timezone.utc), imported[i]),
                             last_login_at=stamp(datetime(2026,10,29,4,20,10,tzinfo=timezone.utc), logged[i])) for i in range(6)]
                async def serve(route):
                    request, url = route.request, urlparse(route.request.url)
                    path = url.path.removeprefix('/okad')
                    q = {k:v[0] for k,v in parse_qs(url.query).items()}
                    if not path.startswith('/api/'):
                        file = FRONT/path.lstrip('/')
                        if not file.is_file(): file=FRONT/('index-okad.html' if prefix else 'index.html')
                        return await route.fulfill(path=str(file),content_type=mimetypes.guess_type(file)[0])
                    if path=='/api/external/groups': data=[]
                    elif path=='/api/auth/me': data=dict(id=1,username='admin',is_active=True,is_superuser=True)
                    elif path=='/api/external/members':
                        calls.append(q); selected=rows[:]
                        for key,field,lower in [('last_login_from','last_login_at',True),('last_login_before','last_login_at',False),('imported_from','created_at',True),('imported_before','created_at',False)]:
                            if q.get(key):
                                boundary=datetime.fromisoformat(q[key].replace('Z','+00:00'))
                                selected=[r for r in selected if r[field] and (datetime.fromisoformat(r[field])>=boundary if lower else datetime.fromisoformat(r[field])<boundary)]
                        field=q.get('sort_by','id');reverse=q.get('sort_order','desc')=='desc'
                        known=[r for r in selected if r[field] is not None]
                        missing=[r for r in selected if r[field] is None]
                        selected=sorted(known,key=lambda r:(r[field],r['id']),reverse=reverse)+sorted(missing,key=lambda r:r['id'],reverse=reverse)
                        size,page=int(q['size']),int(q['page']);data=dict(items=selected[(page-1)*size:page*size],total=len(selected))
                    elif path=='/api/external/members/sub2-stock': data=dict(ok=True,configured=True,items={})
                    elif path in ('/api/external/members/export','/api/external/members/batch-login-filter'):
                        actions.append(request.post_data_json if request.method=='POST' else q)
                        data=dict(queued=0,message='无待重登账号') if path.endswith('filter') else []
                    else:data=[] if path.endswith('/jobs') else dict(items=[],total=0)
                    await route.fulfill(json=data)
                # Input is always Beijing time even when the browser uses another timezone.
                page=await browser.new_page(viewport=dict(width=width,height=1100),timezone_id='America/Los_Angeles',locale='zh-CN')
                page.on('pageerror',lambda e:errors.append(str(e)))
                await page.route('**/*',serve);await page.add_init_script("localStorage.setItem('okad_token','synthetic-time-sort')")
                await page.goto('http://time-sort.test'+prefix+'/external-members')
                await expect(page.locator('#extm-total')).to_have_text('6')
                await expect(page.locator('#extm-f-states')).to_have_count(0)
                assert '账号状态' not in await page.locator('.extv-filter-grid').inner_text()
                await expect(page.locator('.extm-t thead th')).to_have_count(10)
                await expect(page.locator('th[data-sort-column=created_at]')).to_have_text('导入时间')
                for selector in ['#extm-f-import-from','#extm-f-import-to','#extm-f-last-login-from','#extm-f-last-login-to']:
                    await expect(page.locator(selector)).to_have_attribute('type','datetime-local')
                    await expect(page.locator(selector)).to_have_attribute('step','1')
                await page.locator('#extm-page-size-form input').fill('2');await page.locator('#extm-page-size-form button').click()
                await page.locator('#extm-next').click();await expect(page.locator('#extm-page-info')).to_have_text('第 2 / 3 页')
                await page.locator('#extm-f-last-login-from').fill('2026-10-29T12:20:11')
                await page.locator('#extm-f-last-login-to').fill('2026-10-29T12:20:11')
                await expect(page.locator('#extm-total')).to_have_text('3');await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 2 页')
                expected=dict(last_login_from='2026-10-29T04:20:11.000Z',last_login_before='2026-10-29T04:20:12.000Z')
                assert all(calls[-1][k]==v for k,v in expected.items()),calls[-1]
                def sort_button(key):
                    return page.locator(('.extm-mobile-sort ' if width<=600 else '.extm-t thead ')+f'[data-sort="{key}"]')
                async def ids():return await page.locator('tr[data-member]').evaluate_all('(rows)=>rows.map(r=>Number(r.dataset.member))')
                await sort_button('created_at').click()
                await expect(page.locator('th[data-sort-column=created_at]')).to_have_attribute('aria-sort','ascending')
                await expect(page.locator('tr[data-member]').first).to_have_attribute('data-member','3')
                assert await ids()==[3,5],await ids()
                await page.locator('#extm-next').click();await expect(page.locator('tr[data-member]').first).to_have_attribute('data-member','4')
                await sort_button('created_at').click();await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 2 页')
                await expect(page.locator('tr[data-member]').first).to_have_attribute('data-member','4');assert await ids()==[4,5]
                assert calls[-1]['sort_by']=='created_at' and calls[-1]['sort_order']=='desc'
                if width>800:
                    await page.locator('#extm-export').click();await page.locator('#extm-more-actions > summary').click();await page.locator('#extm-login-all').click()
                    await expect(page.locator('#extm-login-all')).to_be_enabled();assert len(actions)==2
                    assert all(all(action[k]==v for k,v in expected.items()) and action['sort_by']=='created_at' and action['sort_order']=='desc' for action in actions),actions
                await sort_button('last_login_at').click();await expect(page.locator('tr[data-member]').first).to_have_attribute('data-member','3')
                await page.locator('#extm-f-last-login-to').fill('2026-10-29T12:20:10')
                await expect(page.get_by_role('alert').filter(has_text='最后登录')).to_have_text('最后登录结束时间不能早于开始时间')
                assert calls[-1]['last_login_before']==expected['last_login_before']
                await page.locator('#extm-f-last-login-to').fill('2026-10-29T12:20:11')
                await page.locator('#extm-f-import-from').fill('2026-10-29T12:10:02');await page.locator('#extm-f-import-to').fill('2026-10-29T12:10:02')
                await expect(page.locator('#extm-total')).to_have_text('3')
                assert calls[-1]['imported_from']=='2026-10-29T04:10:02.000Z' and calls[-1]['imported_before']=='2026-10-29T04:10:03.000Z'
                for cell in await page.locator('tr[data-member] .extm-time-cell time').all():
                    assert __import__('re').fullmatch(r'2026-10-29 \d{2}:\d{2}:\d{2}',await cell.get_attribute('aria-label'))
                await page.locator('#extm-reset-filters').click();await expect(page.locator('#extm-total')).to_have_text('6')
                assert not any(k in calls[-1] for k in ['sort_by','sort_order','last_login_from','last_login_before','imported_from','imported_before','account_states'])
                await sort_button('last_login_at').click()
                await page.locator('#extm-last').click();await expect(page.locator('tr[data-member]').last).to_have_attribute('data-member','1')
                await sort_button('last_login_at').click();await page.locator('#extm-last').click();await expect(page.locator('tr[data-member]').last).to_have_attribute('data-member','1')
                for selector in ['#extm-f-import-from','#extm-f-import-to','#extm-f-last-login-from','#extm-f-last-login-to']:
                    box=await page.locator(selector).bounding_box();assert box and box['x']>=0 and box['x']+box['width']<=width+1,(selector,box,width)
                await page.locator('#extm-reset-filters').click();await page.locator('#extm-embed').evaluate('(n)=>n.scrollTop=0')
                await page.screenshot(path=str(OUT/f'{os.environ.get("FILTER_BROWSER","chromium")}-{prefix.replace("/","") or "root"}-{width}.png'))
                assert not errors,errors
                await page.close()
        await browser.close()
    print('PASS: second-precision ranges, inclusive seconds, global stable ordering, pagination, export/bulk scope, reset, missing times, mobile and 4 routes')

if __name__=='__main__':asyncio.run(main())
