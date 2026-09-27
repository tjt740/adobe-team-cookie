"""Batch relogin scope and copy behavior with synthetic API responses only."""
import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')
ROOT = Path(__file__).resolve().parents[3]


async def main():
    rows = [dict(id=i, email=f'account{i}@example.com', login_status='ok' if i == 3 else 'never',
                 subscription_ok=i == 3, created_at='2026-09-27T00:00:00', latest_job=None)
            for i in range(1, 4)]
    rows[1]['latest_job'] = dict(id=40, type='external_login', status='paused', target=1, success=0, fail=0)
    calls, errors = [], []
    reject = False

    def matches(row, filters):
        return ((not filters.get('keyword') or filters['keyword'] in row['email'])
                and (not filters.get('login_status') or filters['login_status'] == row['login_status'])
                and (filters.get('subscription_ok') is None or filters['subscription_ok'] == row['subscription_ok']))

    async def route_api(route):
        req, url = route.request, urlparse(route.request.url)
        if url.path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif url.path == '/api/external/members':
            filters = {k: v[0] for k, v in parse_qs(url.query).items()}
            if 'subscription_ok' in filters:
                filters['subscription_ok'] = filters['subscription_ok'] == 'true'
            items = [row for row in rows if matches(row, filters)]
            data = dict(items=items, total=len(items))
        elif url.path in ('/api/external/members/batch-login', '/api/external/members/batch-login-filter'):
            calls.append((url.path, req.post_data_json))
            await asyncio.sleep(.3)
            if reject:
                await route.fulfill(status=503, json={'detail': '模拟重登提交失败'})
                return
            selected = url.path.endswith('/batch-login')
            scope = [row for row in rows if row['id'] in req.post_data_json['ids']] if selected else [row for row in rows if matches(row, req.post_data_json)]
            pending = [row for row in scope if not row['latest_job'] or row['latest_job']['status'] == 'done']
            skipped = len(scope) - len(pending)
            job = dict(id=40 + len(calls), type='external_login', status='running', target=len(pending), success=0, fail=0) if pending else None
            for row in pending:
                row['latest_job'] = job
            data = job if selected else dict(job=job, queued=len(pending), skipped=skipped, total=len(scope),
                                             message=f'已提交 {len(pending)} 个账号重登，跳过 {skipped} 个任务未结束的账号')
        elif url.path == '/api/adobe-accounts/jobs':
            data = []
        else:
            data = {'items': [], 'total': 0}
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000}, permissions=['clipboard-read', 'clipboard-write'])
        page = await context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/api/**', route_api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + '/external-members')
        await expect(page.locator('tr[data-member]')).to_have_count(3)
        batch, all_button = page.locator('#extm-batch-login'), page.locator('#extm-login-all')
        await expect(batch).to_be_disabled()
        await expect(all_button).to_have_text('一键重登全部')
        email = page.locator('[data-member="1"] .extm-email')
        await email.click()
        await expect(page.locator('#extm-op')).to_have_text('已复制账号：account1@example.com')
        assert await page.evaluate('navigator.clipboard.readText()') == 'account1@example.com'
        await expect(page.locator('[data-detail]')).to_have_count(0)
        # Keyboard activation and the fallback copy path both copy the exact email.
        await page.evaluate("() => { navigator.clipboard.writeText = async () => { throw new Error('denied'); }; }")
        await page.locator('[data-member="3"] .extm-email').focus()
        await page.keyboard.press('Enter')
        await expect(page.locator('#extm-op')).to_have_text('已复制账号：account3@example.com')
        assert await page.evaluate('navigator.clipboard.readText()') == 'account3@example.com'
        await page.evaluate("() => { document.execCommand = () => false; }")
        await email.click()
        await expect(page.locator('#extm-op')).to_have_text('复制失败，请手动复制账号：account1@example.com')
        await expect(page.locator('[data-detail]')).to_have_count(0)

        await page.locator('[data-member="1"] .extm-rowck').check()
        await page.locator('[data-member="3"] .extm-rowck').check()
        await expect(batch).to_have_text('选中批量重登（2）')
        await batch.click()
        await expect(batch).to_be_disabled()
        await expect(all_button).to_be_disabled()
        await expect(page.locator('[data-login="1"]')).to_be_disabled()
        await expect(page.locator('#extm-op')).to_contain_text('已提交登录任务')
        assert calls[-1] == ('/api/external/members/batch-login', {'ids': [1, 3]})
        # Complete the selected batch, keep the unrelated paused account untouched.
        rows[0]['latest_job']['status'] = 'done'
        await page.locator('#extm-refresh').click()
        await expect(batch).to_be_enabled()
        await page.locator('[data-member="3"] .extm-rowck').uncheck()
        await all_button.click()
        await expect(all_button).to_have_text('提交重登中…')
        await expect(batch).to_be_disabled()
        await expect(page.locator('#extm-op')).to_contain_text('已提交 2 个账号重登，跳过 1 个')
        await expect(all_button).to_be_enabled()
        assert calls[-1] == ('/api/external/members/batch-login-filter', {'keyword': '', 'login_status': None, 'subscription_ok': None})
        assert rows[0]['latest_job'] == rows[2]['latest_job']
        assert rows[1]['latest_job']['id'] == 40
        assert len(calls) == 2
        await page.reload()
        await expect(page.locator('[data-login="1"]')).to_be_disabled()
        await expect(page.locator('[data-login="3"]')).to_be_disabled()
        await all_button.click()
        await expect(page.locator('#extm-op')).to_contain_text('已提交 0 个账号重登，跳过 3 个')
        await expect(all_button).to_be_enabled()

        rows[2]['latest_job']['status'] = 'done'
        await page.locator('#extm-f-kw').fill('account3')
        await page.locator('#extm-f-status').select_option('ok')
        await page.locator('#extm-f-sub').select_option('true')
        await expect(page.locator('tr[data-member]')).to_have_count(1)
        await expect(all_button).to_have_text('一键重登筛选结果')
        await all_button.click()
        await expect(page.locator('#extm-op')).to_contain_text('已提交 1 个账号重登，跳过 0 个')
        assert calls[-1][1] == {'keyword': 'account3', 'login_status': 'ok', 'subscription_ok': True}
        await expect(all_button).to_be_enabled()
        reject = True
        await all_button.click()
        await expect(page.locator('#extm-op')).to_have_text('模拟重登提交失败')
        await expect(all_button).to_be_enabled()
        assert len(calls) == 5
        reject = False
        await page.locator('#extm-f-kw').fill('missing')
        await expect(page.locator('tr[data-member]')).to_have_count(0)
        await all_button.click()
        await expect(page.locator('#extm-op')).to_contain_text('已提交 0 个账号重登，跳过 0 个')
        await expect(all_button).to_be_enabled()
        await page.locator('#extm-f-kw').fill('')
        await page.locator('#extm-f-status').select_option('')
        await page.locator('#extm-f-sub').select_option('')
        await expect(page.locator('tr[data-member]')).to_have_count(3)
        output = ROOT / '.local'
        output.mkdir(exist_ok=True)
        await page.screenshot(path=str(output / 'external-batch-relogin.png'), full_page=True)
        assert not errors, errors
        await browser.close()
    print('PASS: exact email copy, keyboard/fallback/failure, selected/all/filter relogin, busy skips, loading, reload, empty scope and failure recovery')


if __name__ == '__main__':
    asyncio.run(main())
