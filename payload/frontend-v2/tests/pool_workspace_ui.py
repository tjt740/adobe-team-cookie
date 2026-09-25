"""Pool layout, menus, key prerequisite and compact task results. Mocked APIs only."""
import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    rows = [dict(id=i, admin_id=0, admin_email='', email=f'pool{i}@example.com',
                 display_name=f'示例账号 {i}', status='registered', credits=4000, registered=True,
                 is_admin=False, is_imported=True, has_token=True, has_cookie=i == 1,
                 created_at='2026-09-26T00:00:00Z') for i in (1, 2)]
    cfg = dict(admin_token_set=False, base_url='http://sub2.test', platform='adobe', group_ids='2')
    pushes, exports, lists, logins, errors = [], [], [], [], []
    job = dict(id=88, type='pool_cookie_sub2', status='done', target=1, success=1, fail=0,
               extra={'items': [dict(id=1, email='pool1@example.com', status='pushed', message='已推送，在库 Sub2')]})

    async def api(route):
        req, url = route.request, urlparse(route.request.url)
        if url.path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif url.path == '/api/pool':
            lists.append(parse_qs(url.query))
            data = dict(items=rows, total=2, page=1, size=500)
        elif url.path == '/api/sub2/config': data = cfg
        elif url.path == '/api/sub2/pool-membership': data = dict(ok=True, in_sub2=['pool1@example.com'])
        elif url.path == '/api/adobe-accounts/jobs': data = []
        elif url.path == '/api/dashboard/overview':
            data = {'members': {'registered': 2, 'full4000': 2, 'building': 0, 'zero': 0, 'cookie': 1}}
        elif url.path == '/api/pool/login-push-sub2':
            assert cfg['admin_token_set'], 'must never submit without a key'
            pushes.append(req.post_data_json['ids']); data = job
        elif url.path == '/api/pool/batch-login-filter':
            logins.append(req.post_data_json)
            data = dict(id=99, type='pool_login', status='running', target=2, success=0, fail=0)
        elif url.path == '/api/adobe-accounts/jobs/88': data = job
        elif url.path == '/api/pool/export':
            exports.append(parse_qs(url.query))
            await route.fulfill(body='[]', content_type='application/json')
            return
        else: data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1100})
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/api/**', api)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-ui-test')")
        await page.goto(BASE + '/pool')
        await expect(page.locator('.pool-field').nth(1)).to_contain_text('全部')
        await expect(page.locator('.pool-sub2-notice')).to_contain_text('管理员密钥')
        row = page.locator('tbody tr').filter(has_text='pool1@example.com')
        await row.get_by_role('checkbox').click()
        button = page.locator('#pool-sub2-push')
        await expect(button).to_be_disabled()
        assert not pushes
        await page.get_by_role('button', name='Sub2 导入说明', exact=True).click()
        await expect(page.locator('#pool-sub2-help-content')).to_contain_text('未配置密钥时无法导入')
        await page.get_by_role('button', name='去配置 Sub2', exact=True).click()
        await expect(page.locator('#sub2-panel')).to_have_class('on')
        await page.locator('#s2-close').click()
        cfg['admin_token_set'] = True
        await page.evaluate("window.dispatchEvent(new Event('okad:sub2-config-changed'))")
        await expect(page.locator('.pool-sub2-notice')).to_have_count(0)
        await expect(button).to_be_enabled()
        # Key can be revoked after the initial render. The button follows the new state.
        cfg['admin_token_set'] = False
        await page.evaluate("window.dispatchEvent(new Event('okad:sub2-config-changed'))")
        await expect(button).to_be_disabled()
        cfg['admin_token_set'] = True
        await page.evaluate("window.dispatchEvent(new Event('okad:sub2-config-changed'))")
        await expect(button).to_be_enabled()
        # Recheck on submit even when a key change happened without a UI event.
        cfg['admin_token_set'] = False
        await button.click()
        await expect(button).to_be_disabled()
        await expect(page.locator('.pool-job-error')).to_contain_text('管理员密钥')
        assert not pushes
        cfg['admin_token_set'] = True
        await page.evaluate("window.dispatchEvent(new Event('okad:sub2-config-changed'))")
        await expect(button).to_be_enabled()
        await button.click()
        await expect(page.locator('#pool-sub2-progress')).to_contain_text('已完成')
        assert pushes == [[1]]
        await expect(page.locator('.pool-job-item')).to_have_count(0)
        await page.get_by_role('button', name='展开明细', exact=True).click()
        await expect(page.locator('.pool-job-item')).to_have_count(1)
        await page.get_by_role('button', name='收起明细', exact=True).click()
        # The export-state filter is now a real request parameter, not an injected decoration.
        await page.locator('.pool-field').last.locator('.n-base-selection').click()
        await page.get_by_text('未导出', exact=True).last.click()
        await expect(page.locator('.pool-field').last).to_contain_text('未导出')
        await page.get_by_role('button', name='导出 ▾', exact=True).click()
        async with page.expect_download():
            await page.get_by_text('导出 Cookie', exact=True).click()
        assert exports[-1]['format'] == ['cookies'] and exports[-1]['export_status'] == ['unexported']
        assert lists[-1]['export_status'] == ['unexported']
        await row.get_by_role('button', name='更多 ▾', exact=True).click()
        await expect(page.get_by_text('测试收件', exact=True)).to_be_visible()
        await expect(page.get_by_text('刷新 AT', exact=True)).to_be_visible()
        await expect(page.get_by_text('刷新 ARP', exact=True)).to_be_visible()
        await expect(page.get_by_text('测试出图', exact=True)).to_be_visible()
        await page.get_by_role('heading', name='账号列表', exact=True).click()
        await expect(page.get_by_text('测试收件', exact=True)).not_to_be_visible()
        await page.get_by_placeholder('搜索邮箱', exact=True).fill('pool1')
        await page.get_by_role('button', name='重置', exact=True).click()
        await expect(page.get_by_placeholder('搜索邮箱', exact=True)).to_have_value('')
        await expect(page.get_by_text('已开始下载', exact=True)).not_to_be_visible()
        for width in (1440, 1024, 768):
            await page.set_viewport_size({'width': width, 'height': 1100})
            await expect(page.locator('#pool-sub2-help')).to_be_visible()
            overflow = await page.locator('#pool-workspace').evaluate('(el)=>el.scrollWidth>el.clientWidth+2')
            assert not overflow, f'workspace overflows at {width}'
            await page.screenshot(path=str(Path(__file__).resolve().parents[3] / f'.local/pool-workspace-{width}.png'), full_page=True)
        await page.locator('.pool-field').last.locator('.n-base-selection').click()
        await page.get_by_text('未导出', exact=True).last.click()
        await page.get_by_role('button', name='登录筛选结果', exact=True).click()
        await page.get_by_role('button', name='确认', exact=True).click()
        await page.wait_for_url('**/jobs?id=99')
        assert logins[-1]['export_status'] == 'unexported'
        assert logins[-1]['has_token'] is None and logins[-1]['pool_type'] == 'all'
        assert not errors, errors
        await browser.close()
    print('PASS: key gating, question-mark help, configuration navigation/update, selected import, folded results, menus, filters and responsive layout')


if __name__ == '__main__':
    asyncio.run(main())
