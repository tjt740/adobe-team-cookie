"""Exercise the actual prebuilt pool page with synthetic accounts and APIs."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    rows = [dict(id=i, admin_id=0, admin_email='', email=f'pool{i}@example.com',
                 display_name=f'测试账号 {i}', status='registered', credits=4000,
                 registered=True, is_admin=False, is_imported=True, has_token=True,
                 has_cookie=False, has_arp=False, created_at='2026-09-26T00:00:00Z') for i in (1, 2, 3)]
    stock = ['pool3@example.com']
    pushes, errors = [], []
    job = dict(id=99, type='pool_cookie_sub2', status='running', target=2, success=0, fail=0,
               extra={'items': []})
    reject = False

    async def route_api(route):
        path = urlparse(route.request.url).path
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/pool':
            data = dict(items=rows, total=3, page=1, size=500)
        elif path == '/api/sub2/pool-membership':
            data = {'ok': True, 'in_sub2': stock}
        elif path == '/api/sub2/config':
            data = {'admin_token_set': True, 'base_url': 'http://sub2.test', 'platform': 'adobe', 'group_ids': '2'}
        elif path == '/api/pool/login-push-sub2':
            pushes.append(route.request.post_data_json['ids'])
            if reject:
                await route.fulfill(status=400, json={'detail': '请先在 Sub2 管理选择并保存 Adobe 分组'})
                return
            job['extra']['items'] = [dict(id=i, email=f'pool{i}@example.com',
                                        status='login', message='正在登录 Adobe，获取 Cookie') for i in pushes[-1]]
            data = job
        elif path == '/api/adobe-accounts/jobs/99':
            data = job
        elif path == '/api/adobe-accounts/jobs':
            data = [job] if pushes else []
        elif path == '/api/dashboard/stats':
            data = {'members': {'registered': 3, 'full4000': 3, 'building': 0, 'zero': 0,
                                'cookie': sum(bool(r['has_cookie']) for r in rows)}}
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1600, 'height': 1100})
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/api/**', route_api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/pool')
        button = page.locator('#pool-sub2-push')
        await expect(button).to_be_disabled()
        for i in (1, 2):
            row = page.locator('tbody tr').filter(has_text=f'pool{i}@example.com')
            await row.get_by_role('checkbox').click()
        await expect(page.locator('.pool-selection')).to_contain_text('已选 2 个')
        await expect(button).to_be_enabled()
        await button.click()
        await expect(button).to_be_disabled()
        await expect(page.locator('[data-pool-sub2-id="1"]')).to_contain_text('正在登录')
        assert pushes == [[1, 2]]
        # Reload resumes tracking the same task, without repeating the POST.
        await page.reload()
        await expect(button).to_be_disabled()
        await expect(page.locator('[data-pool-sub2-id="2"]')).to_contain_text('获取 Cookie')
        job.update(status='done', success=1, fail=1)
        job['extra']['items'][0].update(status='pushed', message='已推送，在库 Sub2')
        job['extra']['items'][1].update(status='failed', message='验证码获取失败，请检查取信配置')
        rows[0]['has_cookie'] = True
        stock.append('pool1@example.com')
        await expect(page.locator('#pool-sub2-progress')).to_contain_text('已完成', timeout=8000)
        await expect(page.locator('[data-pool-sub2-id="2"]')).to_contain_text('验证码获取失败')
        await expect(page.locator('tbody tr').filter(has_text='pool1@example.com')).to_contain_text('在库 Sub2')
        await expect(page.locator('tbody tr').filter(has_text='pool2@example.com')).to_contain_text('未推送')
        assert pushes == [[1, 2]]
        reject = True
        await page.locator('tbody tr').filter(has_text='pool2@example.com').get_by_role('checkbox').click()
        await button.click()
        await expect(page.get_by_role('alert')).to_contain_text('保存 Adobe 分组')
        await expect(button).to_be_enabled()
        assert pushes == [[1, 2], [2]]
        await page.screenshot(path=str(Path(__file__).resolve().parents[3] / '.local/pool-sub2-ui.png'), full_page=True)
        assert not errors, errors
        await browser.close()
    print('PASS: pool selection, task progress/resume, partial failure, stock refresh, selected retry and config errors')


if __name__ == '__main__':
    asyncio.run(main())
