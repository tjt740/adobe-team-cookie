"""Real control interactions: state tags, date calendar, raw credit bounds and 500/page."""
import asyncio
import os
from datetime import datetime
import mimetypes
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.async_api import async_playwright,expect
from external_controls import select_value

FRONT=Path(__file__).resolve().parents[1]
OUT=FRONT.parents[1]/'.local'/'filter-repair-preview'

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await getattr(p,os.environ.get('FILTER_BROWSER','chromium')).launch()
        for prefix in ('','/okad'):
            calls,errors=[],[]
            rows=[dict(id=i,email=f'filter{i:04d}@example.test',login_status='ok',has_cookie=True,
                       credits_available=[0,4000,4000.5,None][i%4],credits_total=5000,subscription_ok=True,
                       created_at=f'2026-10-{10+i%5:02d}T08:00:00Z') for i in range(1,1124)]
            async def serve(route):
                url=urlparse(route.request.url);path=url.path.removeprefix('/okad');q=parse_qs(url.query)
                if not path.startswith('/api/'):
                    file=FRONT/path.lstrip('/')
                    if not file.is_file():file=FRONT/('index-okad.html' if prefix else 'index.html')
                    return await route.fulfill(path=str(file),content_type=mimetypes.guess_type(file)[0])
                if path=='/api/auth/me':data=dict(id=1,username='admin',is_active=True,is_superuser=True)
                elif path=='/api/external/members':
                    calls.append(q)
                    selected=rows
                    if q.get('account_states'):selected=[r for r in selected if 'sub2_'+str([408,401,503][r['id']%3]) in q['account_states']]
                    for key in ('credits_min','credits_max'):
                        if key in q:
                            field='credits_'+q.get('credits_field',['available'])[0];v=float(q[key][0])
                            selected=[r for r in selected if r[field] is not None and (r[field]>=v if key=='credits_min' else r[field]<=v)]
                    for key in ('imported_from','imported_before'):
                        if key in q:
                            boundary=datetime.fromisoformat(q[key][0])
                            selected=[r for r in selected if (datetime.fromisoformat(r['created_at'])>=boundary if key=='imported_from' else datetime.fromisoformat(r['created_at'])<boundary)]
                    size=int(q['size'][0]);page=int(q['page'][0]);data=dict(items=selected[(page-1)*size:page*size],total=len(selected))
                elif path=='/api/external/members/sub2-stock':data=dict(ok=True,configured=True,items={})
                else:data=[] if path.endswith('/jobs') else dict(items=[],total=0)
                await route.fulfill(json=data)
            page=await browser.new_page(viewport={'width':1440,'height':1050},timezone_id='Asia/Shanghai',locale='zh-CN')
            page.on('pageerror',lambda e:errors.append(str(e)))
            await page.route('**/*',serve);await page.add_init_script("localStorage.setItem('okad_token','synthetic-filter-repair')")
            await page.goto('http://filters.test'+prefix+'/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(500)
            await expect(page.locator('#extm-page-size')).to_have_value('500')
            await expect(page.locator('#extm-page-size-form input[name=pageSize]')).to_have_value('500')
            assert calls[-1]['size']==['500']
            await page.locator('#extm-next').click();await expect(page.locator('tr[data-member]')).to_have_count(500)
            await expect(page.locator('tr[data-member]').first).to_have_attribute('data-member','501')
            await page.locator('#extm-last').click();await expect(page.locator('tr[data-member]')).to_have_count(123)
            await page.locator('#extm-page-size').select_option('50');await expect(page.locator('tr[data-member]')).to_have_count(50)
            await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 23 页')
            await page.locator('#extm-page-size-form input[name=pageSize]').fill('137')
            await page.locator('#extm-page-size-form button').click();await expect(page.locator('tr[data-member]')).to_have_count(137)
            await expect(page.locator('#extm-page-size')).to_have_value('137')
            # The status field immediately follows email in reading and visual order.
            fields=await page.locator('.extf-grid>.extf-field>label').all_text_contents()
            assert fields[:2]==['邮箱','账号状态'],fields
            state=page.locator('#extm-f-states')
            await state.locator('.n-base-selection').click()
            page.set_default_timeout(5000)
            for text in ['Sub2 408 · 请求超时','Sub2 401 · 鉴权失败','Sub2 503']:
                await state.locator('input').fill(text)
                await page.locator('.n-base-select-option:visible').filter(has=page.get_by_text(text,exact=True)).click()
            await page.keyboard.press('Escape')
            await expect(page.locator('#extf-state-help')).to_have_text('已选 3 个状态，满足任一即可')
            assert set(calls[-1]['account_states'])=={'sub2_401','sub2_408','sub2_503'}
            await page.screenshot(path=str(OUT/f'selected-{prefix.replace("/","") or "root"}.png'))
            # Every rendered tag/count must have legible nonempty text and room for it.
            tags=await state.locator('.n-tag').evaluate_all('(els)=>els.filter(e=>e.getBoundingClientRect().width).map(e=>({text:e.innerText.trim(),width:e.getBoundingClientRect().width}))')
            assert tags and all(t['text'] and t['width']>=24 for t in tags),tags
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('#extf-state-help')).to_have_text('账号状态支持多选')
            # Calendar opens from the trigger and supports reversed click order with inclusive end.
            await page.locator('#extm-f-import-range').click()
            dialog=page.locator('#extm-import-date-dialog');await expect(dialog).to_be_visible()
            await dialog.locator('#extm-f-import-from').fill('2026-10-01')
            await dialog.locator('#extm-f-import-to').fill('2026-10-01')
            await dialog.locator('#extm-date-apply').click()
            await page.locator('#extm-f-import-range').click()
            heading=dialog.locator('.extf-calendar-month h4').first
            first_month=await heading.inner_text()
            await dialog.get_by_role('button',name='下个月',exact=True).click();await expect(heading).not_to_have_text(first_month)
            await dialog.get_by_role('button',name='上个月',exact=True).click();await expect(heading).to_have_text(first_month)
            await dialog.locator('[data-date="2026-10-12"]').focus()
            await page.keyboard.press('ArrowRight');await expect(dialog.locator('[data-date="2026-10-13"]')).to_be_focused()
            await dialog.locator('[data-date="2026-10-12"]').click()
            await dialog.locator('[data-date="2026-10-10"]').click()
            await expect(dialog.locator('#extm-f-import-from')).to_have_value('2026-10-10')
            await expect(dialog.locator('#extm-f-import-to')).to_have_value('2026-10-12')
            await dialog.screenshot(path=str(OUT/'calendar-desktop.png'))
            await dialog.locator('#extm-date-apply').click();await expect(dialog).to_be_hidden()
            await expect(page.locator('#extm-results')).to_have_attribute('aria-busy','false')
            assert calls[-1]['imported_from']==['2026-10-09T16:00:00.000Z'],calls[-1]
            assert calls[-1]['imported_before']==['2026-10-12T16:00:00.000Z'],calls[-1]
            await page.locator('#extm-f-import-range').click()
            await dialog.locator('#extm-f-import-from').fill('2026-02-30')
            await dialog.locator('#extm-date-apply').click()
            await expect(dialog.get_by_role('alert')).to_contain_text('有效日期')
            await dialog.locator('#extm-f-import-from').fill('2026-10-14')
            await dialog.locator('#extm-date-apply').click();await expect(dialog.get_by_role('alert')).to_have_text('结束日期不能早于开始日期')
            await dialog.get_by_role('button',name='取消',exact=True).click()
            await expect(page.locator('#extm-f-import-range')).to_contain_text('2026-10-10')
            await page.locator('#extm-f-import-range').click()
            await dialog.get_by_role('button',name='最近 7 天',exact=True).click()
            today=await page.evaluate('()=>{let d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-")}')
            await expect(dialog.locator('#extm-f-import-to')).to_have_value(today)
            await page.keyboard.press('Escape');await expect(dialog).to_be_hidden()
            await page.locator('#extm-f-import-range').click();await dialog.get_by_role('button',name='清除日期',exact=True).click()
            await expect(page.locator('#extm-f-import-range')).to_contain_text('开始日期')
            # Credit editing uses raw input: 0 and decimals survive; invalid input is never silently reused.
            minimum=page.locator('#extm-f-credits-min');maximum=page.locator('#extm-f-credits-max')
            await minimum.fill('0');await maximum.fill('0');await maximum.press('Enter')
            await expect(page.locator('#extm-results')).to_have_attribute('aria-busy','false')
            await expect(maximum).to_have_value('0')
            assert calls[-1]['credits_min']==calls[-1]['credits_max']==['0'],calls[-1]
            last_total=await page.locator('#extm-total').inner_text()
            for invalid in ['-1','abc','NaN','1e999']:
                await minimum.fill(invalid);await minimum.press('Enter')
                await expect(page.locator('#extf-credit-error')).to_contain_text('有效数字')
                await expect(minimum).to_have_value(invalid)
                await expect(page.locator('#extm-total')).to_have_text(last_total)
                assert calls[-1]['credits_min']==['0']
            await minimum.fill('4000.5');await maximum.fill('4000');await maximum.press('Enter')
            await expect(page.locator('#extf-credit-error')).to_have_text('积分最大值不能小于最小值')
            await maximum.fill('4000.5');await maximum.press('Enter')
            await expect(page.locator('#extf-credit-error')).to_have_count(0)
            await expect(page.locator('#extm-results')).to_have_attribute('aria-busy','false')
            assert calls[-1]['credits_min']==calls[-1]['credits_max']==['4000.5'],calls[-1]
            await expect(page.locator('tr[data-member]').first.locator('td').nth(3)).to_contain_text('4000.5')
            await maximum.fill('');await minimum.fill('');await minimum.press('Enter')
            await expect(page.locator('#extm-total')).to_have_text('1123')
            assert 'credits_min' not in calls[-1] and 'credits_max' not in calls[-1]
            await state.locator('.n-base-selection').click()
            for label in ['Sub2 408 · 请求超时','Sub2 401 · 鉴权失败','Sub2 503']:
                await state.locator('input').fill(label)
                await page.locator('.n-base-select-option:visible').filter(has=page.get_by_text(label,exact=True)).click()
            await page.keyboard.press('Escape')
            # Keep all controls and the calendar within the viewport, including live count tags.
            for width in [2550,1440,768,390,320]:
                await page.set_viewport_size({'width':width,'height':1050})
                toggle=page.locator('#extm-filters .ws-filter-toggle')
                if await toggle.is_visible() and await toggle.get_attribute('aria-expanded')=='false':await toggle.click()
                for selector in ['#extm-f-states','#extm-f-import-range','#extm-f-credits-min','#extm-f-credits-max','#extm-refresh','#extm-reset-filters']:
                    box=await page.locator(selector).bounding_box()
                    assert box and box['x']>=-1 and box['x']+box['width']<=width+1,(width,selector,box)
                tags=await state.locator('.n-tag').evaluate_all('(els)=>els.filter(e=>e.getBoundingClientRect().width).map(e=>({text:e.innerText.trim(),width:e.getBoundingClientRect().width}))')
                assert tags and all(t['text'] and t['width']>=24 for t in tags),(width,tags)
                await page.locator('#extm-f-import-range').click();await expect(dialog).to_be_visible()
                box=await dialog.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1,(width,box)
                if width==390:await dialog.screenshot(path=str(OUT/'calendar-mobile.png'))
                await page.keyboard.press('Escape');await expect(dialog).to_be_hidden()
                await page.screenshot(path=str(OUT/f'layout-{width}.png'))
            await page.evaluate("localStorage.setItem('okad-theme','dark')")
            await page.reload();await expect(page.locator('#extm-page-size')).to_have_value('500')
            await page.locator('#extm-filters .ws-filter-toggle').click()
            await page.locator('#extm-f-import-range').click();await expect(dialog).to_be_visible()
            assert await dialog.evaluate('e=>getComputedStyle(e).backgroundColor')!='rgb(255, 255, 255)'
            await dialog.screenshot(path=str(OUT/'calendar-dark.png'))
            assert not errors,errors
            await page.close()
        await browser.close()
    print('PASS: 500 default/custom pagination, status order/tags, real date calendar/validation/cancel/clear, credit zero/decimals/invalid input, responsive layouts and dark theme on both paths')

if __name__=='__main__':asyncio.run(main())
