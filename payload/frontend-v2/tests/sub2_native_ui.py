"""Native Adobe Sub2 panel regression with synthetic API responses only."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    cfg = dict(base_url='https://sub2.example', platform='adobe', protocol='default',
               group_ids='7', enabled=False, auto_push=False, admin_token_set=True)
    calls = []

    async def route_api(route):
        path = urlparse(route.request.url).path
        calls.append((route.request.method, path))
        if path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/sub2/config':
            data = cfg
        elif path == '/api/sub2/groups':
            data = dict(ok=True, groups=[dict(id=7, name='Adobe images', platform='adobe'), dict(id=8, name='OpenAI', platform='openai')])
        elif path == '/api/sub2/accounts':
            data = dict(ok=True, total=1, items=[dict(id=4, name='test@example.com', status='active', group_ids=[7], token_exp='2027-01-01T00:00:00Z')])
        elif path == '/api/sub2/candidates':
            data = dict(sub2_ok=True, sub2_total=1, new_count=0)
        elif path == '/api/sub2/batch-refresh':
            assert route.request.post_data_json == {'account_ids': [4], 'balance': True}
            data = dict(ok=True, result={'usage': {'4': {'adobe_credit': {'usage_limit': 4000, 'current_usage': 100}}}})
        elif path == '/api/sub2/test':
            data = dict(ok=True, message='连接成功,令牌有效')
        elif path == '/api/adobe-accounts/jobs':
            data = []
        elif path == '/api/settings':
            data = {'concurrency': 2}
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/api/**', route_api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/dashboard')
        await page.locator('#sub2-nav-mng').click()
        await expect(page.locator('#s2-tbody')).to_contain_text('test@example.com')
        await expect(page.locator('#s2-st-total')).to_have_text('1')
        await page.locator('#s2-cfghd').click()
        await expect(page.locator('#s2-plat')).to_have_value('adobe')
        await expect(page.locator('#s2-proto')).to_be_hidden()
        await expect(page.locator('#s2-groups')).to_contain_text('Adobe images')
        await expect(page.locator('#s2-groups')).not_to_contain_text('OpenAI')
        await page.locator('#s2-test').click()
        await expect(page.locator('#s2-conn-t')).to_have_text('已连接')
        await page.locator('.s2-rowck').check()
        await page.locator('#s2-bbal').click()
        await expect(page.locator('#s2-tbody')).to_contain_text('3900/4000')
        await expect(page.locator('#s2-tbody')).to_contain_text('27-1-1')
        assert not any(path.endswith('/push') or path.endswith('/batch-delete') for _, path in calls)
        assert not errors, errors
        out = Path(__file__).resolve().parents[3] / '.local/sub2-native-ui.png'
        await page.screenshot(path=str(out), full_page=True)
        await browser.close()
    print('PASS: native platform, groups, account list, connection status, refreshed credits, ISO expiry')


if __name__ == '__main__':
    asyncio.run(main())
