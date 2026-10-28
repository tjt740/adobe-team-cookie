"""Last login dates: local assets, synthetic data, and no real login jobs."""
import asyncio
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.async_api import async_playwright, expect

FRONT = Path(os.environ.get('FILTER_FRONT', str(Path(__file__).resolve().parents[1])))
OUT = Path(__file__).resolve().parents[3] / '.local' / 'last-login-preview'

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('FILTER_BROWSER', 'chromium')).launch()
        for prefix in ('', '/okad'):
            for width in (1440, 390):
                calls, actions, errors = [], [], []
                stamps = [None, '2026-10-27T15:59:59Z', '2026-10-27T16:00:00Z', '2026-10-28T15:59:59Z', '2026-10-28T16:00:00Z']
                rows = [dict(id=i+1, email=f'login{i}@example.test', login_status='ok' if stamp else 'never',
                             has_cookie=True, created_at='2026-10-20T00:00:00Z', last_login_at=stamp)
                        for i, stamp in enumerate(stamps)]
                async def serve(route):
                    request = route.request
                    url = urlparse(request.url)
                    path = url.path.removeprefix('/okad')
                    q = {k:v[0] for k,v in parse_qs(url.query).items()}
                    if not path.startswith('/api/'):
                        file = FRONT / path.lstrip('/')
                        if not file.is_file(): file = FRONT / ('index-okad.html' if prefix else 'index.html')
                        return await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])
                    if path == '/api/external/groups': data = []
                    elif path == '/api/auth/me': data = dict(id=1, username='admin', is_active=True, is_superuser=True)
                    elif path == '/api/external/members':
                        calls.append(q)
                        selected = rows
                        for key, field, lower in [('last_login_from','last_login_at',True),('last_login_before','last_login_at',False),('imported_before','created_at',False)]:
                            if q.get(key):
                                boundary = datetime.fromisoformat(q[key].replace('Z','+00:00'))
                                selected = [r for r in selected if r[field] and (datetime.fromisoformat(r[field].replace('Z','+00:00')) >= boundary if lower else datetime.fromisoformat(r[field].replace('Z','+00:00')) < boundary)]
                        size, page = int(q['size']), int(q['page'])
                        data = dict(items=selected[(page-1)*size:page*size], total=len(selected))
                    elif path == '/api/external/members/sub2-stock': data = dict(ok=True, configured=True, items={})
                    elif path in ('/api/external/members/export','/api/external/members/batch-login-filter'):
                        actions.append(request.post_data_json if request.method == 'POST' else q)
                        data = dict(queued=0, message='无待重登账号') if path.endswith('filter') else []
                    else: data = [] if path.endswith('/jobs') else dict(items=[], total=0)
                    await route.fulfill(json=data)
                # Dates always use Beijing boundaries, even when the browser uses another timezone.
                page = await browser.new_page(viewport=dict(width=width,height=1050),timezone_id='America/Los_Angeles',locale='zh-CN')
                page.on('pageerror',lambda e:errors.append(str(e)))
                await page.route('**/*',serve)
                await page.add_init_script("localStorage.setItem('okad_token','synthetic-last-login')")
                await page.goto('http://login-filter.test'+prefix+'/external-members')
                await expect(page.locator('#extm-total')).to_have_text('5')
                if not await page.locator('#extm-f-last-login-from').is_visible():
                    await page.locator('.ws-filter-toggle').click()
                await page.locator('#extm-page-size-form input').fill('1')
                await page.locator('#extm-page-size-form button').click()
                await page.locator('#extm-next').click()
                await expect(page.locator('#extm-page-info')).to_have_text('第 2 / 5 页')
                await page.locator('#extm-f-last-login-from').fill('2026-10-28')
                await expect(page.locator('#extm-total')).to_have_text('3')
                await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 3 页')
                await page.locator('#extm-f-last-login-to').fill('2026-10-28')
                await expect(page.locator('#extm-total')).to_have_text('2')
                expected = dict(last_login_from='2026-10-27T16:00:00.000Z',last_login_before='2026-10-28T16:00:00.000Z')
                assert all(calls[-1][k]==v for k,v in expected.items()),calls[-1]
                if width > 800:
                    await page.locator('#extm-export').click()
                    await page.locator('#extm-more-actions > summary').click()
                    await page.locator('#extm-login-all').click()
                    await expect(page.locator('#extm-login-all')).to_be_enabled()
                    assert len(actions)==2,actions
                    assert all(all(action[k]==v for k,v in expected.items()) for action in actions),actions
                await page.locator('#extm-f-last-login-to').fill('2026-10-27')
                await expect(page.get_by_role('alert').filter(has_text='最后登录时间')).to_have_text('最后登录时间的结束日期不能早于开始日期')
                assert calls[-1]['last_login_before']==expected['last_login_before']
                await page.locator('#extm-f-last-login-to').fill('2026-10-28')
                await page.locator('#extm-f-last-login-from').fill('')
                await expect(page.locator('#extm-total')).to_have_text('3')
                assert 'last_login_from' not in calls[-1]
                await page.locator('#extm-f-import-to').fill('2026-10-19')
                await expect(page.locator('#extm-total')).to_have_text('0')
                await page.locator('#extm-reset-filters').click()
                await expect(page.locator('#extm-total')).to_have_text('5')
                await expect(page.locator('#extm-f-last-login-from')).to_have_value('')
                await expect(page.locator('#extm-f-last-login-to')).to_have_value('')
                assert not any(k.startswith('last_login_') for k in calls[-1])
                for selector in ('#extm-f-last-login-from','#extm-f-last-login-to'):
                    box = await page.locator(selector).bounding_box()
                    assert box and box['x']>=0 and box['x']+box['width']<=width+1,(selector,box,width)
                await page.locator('#extm-embed').evaluate('(n)=>n.scrollTop=0')
                await page.screenshot(path=str(OUT/f'{prefix.replace("/","") or "root"}-{width}.png'))
                assert not errors,errors
                await page.close()
        await browser.close()
    print('PASS: last login date bounds, pagination, export, batch login, validation, reset, Beijing timezone and 4 responsive routes')

if __name__ == '__main__': asyncio.run(main())
