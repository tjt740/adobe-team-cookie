"""Local browser regression: Sub2 health badges, filters and live refresh."""
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

FRONT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parents[3] / '.local'


async def main():
    rows = [dict(id=i, email=f'health{i:03d}@example.test', login_status='ok', has_cookie=True,
                 subscription_ok=True, credits_total=4000, created_at='2026-10-14T00:00:00Z')
            for i in range(1, 246)]
    state = dict(fail=False, recovered=False)
    calls, actions, errors = [], [], []

    def health(row):
        code = 401 if row['id'] <= 220 else 408 if row['id'] < 245 else 503
        if state['recovered'] and row['id'] == 1:
            return dict(state='recovered', codes=[], errors=[])
        return dict(state='error', codes=[code], errors=[dict(code=code)])

    def matches(query):
        value = query.get('sub2_health')
        return [r for r in rows if not value or
                (value.isdigit() and int(value) in health(r)['codes']) or
                (value == health(r)['state']) or
                (value == 'other' and any(c not in (401, 408) for c in health(r)['codes']))]

    async def serve(route):
        request, url = route.request, urlparse(route.request.url)
        path = url.path.removeprefix('/okad')
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        if not path.startswith('/api/'):
            file = FRONT / path.lstrip('/')
            if not file.is_file():
                file = FRONT / ('index-okad.html' if url.path.startswith('/okad/') else 'index.html')
            await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])
            return
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/external/members':
            calls.append(query)
            if state['fail'] and query.get('sub2_health'):
                await route.fulfill(status=503, json={'detail': 'Sub2 库存暂不可用'})
                return
            selected = matches(query)
            page, size = int(query['page']), int(query['size'])
            data = dict(items=selected[(page-1)*size:page*size], total=len(selected))
        elif path == '/api/external/members/sub2-stock':
            data = dict(ok=not state['fail'], configured=True, checked_at='2026-10-14T12:00:00Z',
                        items={} if state['fail'] else {r['id']: dict(email=r['email'], in_stock=True, account_ids=[r['id']], account_health=health(r)) for r in rows})
        elif path == '/api/external/members/export':
            actions.append(query)
            data = []
        else:
            data = [] if path.endswith('/jobs') else dict(items=[], total=0)
        await route.fulfill(json=data)

    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            state.update(fail=False, recovered=False)
            page = await browser.new_page(viewport={'width': 1440, 'height': 1000}, timezone_id='Asia/Shanghai')
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.route('**/*', serve)
            await page.add_init_script("localStorage.setItem('okad_token','synthetic-health-test')")
            await page.goto('http://okad.test' + prefix + '/external-members')
            await expect(page.locator('tr[data-member]')).to_have_count(200)
            await expect(page.locator('tr[data-member="1"] [data-sub2-health]')).to_have_text('Sub2 401')
            await expect(page.locator('tr[data-member="1"] [data-sub2-health]')).to_have_class('extm-pill bad')
            await page.locator('#extm-f-health').select_option('401')
            await expect(page.locator('#extm-total')).to_have_text('220')
            await page.locator('#extm-next').click()
            await expect(page.locator('tr[data-member]')).to_have_count(20)
            await page.locator('tr[data-member] .extm-rowck').first.check()
            await page.locator('#extm-f-health').select_option('408')
            await expect(page.locator('#extm-selc')).to_have_text('0')
            await expect(page.locator('#extm-total')).to_have_text('24')
            await expect(page.locator('#extm-page-info')).to_have_text('第 1 / 1 页')
            await expect(page.locator('[data-sub2-health]').first).to_have_class('extm-pill warn')
            await page.locator('#extm-export').click()
            await expect(page.locator('#extm-export')).to_be_enabled()
            assert actions[-1]['sub2_health'] == '408'
            await page.locator('#extm-f-health').select_option('other')
            await expect(page.locator('#extm-total')).to_have_text('1')
            await expect(page.locator('[data-sub2-health]')).to_have_text('Sub2 503')
            await page.locator('#extm-reset-filters').click()
            await expect(page.locator('#extm-f-health')).to_have_value('')
            state['recovered'] = True
            await page.locator('#extm-refresh').click()
            await expect(page.locator('tr[data-member="1"] [data-sub2-health]')).to_have_text('Sub2 已有成功证据')
            state['fail'] = True
            await page.locator('#extm-refresh').click()
            await expect(page.locator('tr[data-member="1"] [data-sub2-health]')).to_have_text('Sub2 状态暂不可用')
            await page.locator('#extm-f-health').select_option('401')
            await expect(page.locator('#extm-tbody')).to_contain_text('Sub2 库存暂不可用')
            state.update(fail=False, recovered=False)
            await page.locator('#extm-refresh').click()
            await expect(page.locator('#extm-total')).to_have_text('220')
            await page.locator('#extm-f-health').select_option('408')
            await expect(page.locator('#extm-total')).to_have_text('24')
            await page.locator('.extm-import-card').first.locator('summary').click()
            await page.screenshot(path=str(OUTPUT / ('sub2-health-' + ('okad' if prefix else 'root') + '.png')))
            await page.set_viewport_size({'width': 393, 'height': 852})
            await expect(page.locator('#extm-f-health')).to_be_visible()
            await page.screenshot(path=str(OUTPUT / 'sub2-health-mobile.png'))
            await page.close()
        assert not errors, errors
        await browser.close()
    print('PASS: health colors, pagination, filters, export scope, recovery, unavailable state, root and /okad, mobile')


asyncio.run(main())
