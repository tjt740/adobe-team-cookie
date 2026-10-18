"""Manual Sub2 push consent, with all API calls intercepted."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18082')
ROOT = Path(__file__).resolve().parents[3]


async def main():
    rows = [dict(id=i, email=f'account{i}@example.test', login_status='ok', first_login_done=True,
                 has_cookie=True, subscription_ok=True, credits_available=0, credits_total=4000,
                 sub2_status='synced', message='登录成功', created_at='2026-10-11T04:00:00Z')
            for i in range(1, 5)]
    rows[1].update(subscription_ok=False, credits_total=10)
    rows[2].update(credits_total=None, credits_available=None)
    rows[3].update(credits_total=None, credits_available=None,
                   credits_error='Adobe 拒绝查询（HTTP 451 / 10009）<img src=x onerror=alert(1)>')
    writes = []

    async def api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix('/okad')
        if req.method != 'GET':
            writes.append((path, req.post_data_json))
            assert path in ('/api/external/members/push-sub2', '/api/external/members/relink-sub2')
            await asyncio.sleep(.15)
            data = dict(queued=len(req.post_data_json['ids']), message='已提交同步')
        elif path == '/api/auth/me':
            data = dict(id=1, username='preview', is_active=True, is_superuser=True)
        elif path == '/api/external/members':
            data = dict(items=rows, total=len(rows))
        elif path == '/api/external/members/sub2-stock':
            data = dict(ok=True, configured=True, items={})
        elif path == '/api/adobe-accounts/jobs':
            data = []
        elif path == '/api/settings':
            data = dict(concurrency=5)
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport=dict(width=1440, height=1000))
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/api/**', api)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-subscription-test')")
        await page.goto(BASE + '/external-members', wait_until='networkidle')
        push = page.locator('#extm-sub2-push')
        dialog = page.locator('#extm-sub2-confirm-dialog')

        async def select(ids):
            for i in range(1, 5):
                await page.locator(f'[data-member="{i}"] .extm-rowck').set_checked(i in ids)

        # A zero available balance with a valid subscription needs no warning.
        await select([1]); await push.click()
        await expect(push).to_be_enabled()
        assert writes == [('/api/external/members/push-sub2', {'ids': [1]})]
        await expect(dialog).to_have_count(0)
        writes.clear()

        # Every abnormal account is named; healthy selected accounts are counted
        # in the push scope, but not incorrectly listed as abnormal.
        await select([1, 2, 3, 4]); await push.click()
        await expect(dialog).to_be_visible()
        await expect(dialog).to_contain_text('已选 4 个账号，其中 3 个订阅异常或状态未知')
        await expect(dialog.locator('li')).to_have_count(3)
        await expect(dialog.locator('ul')).not_to_contain_text(rows[0]['email'])
        for i in (1, 2, 3):
            await expect(dialog).to_contain_text(rows[i]['email'])
        await expect(dialog).to_contain_text('掉订阅')
        await expect(dialog).to_contain_text('积分未查到')
        await expect(dialog).to_contain_text('HTTP 451 / 10009')
        assert await dialog.locator('img').count() == 0
        await expect(dialog.locator('[data-cancel]')).to_be_focused()
        assert not writes
        await page.screenshot(path=str(ROOT / '.local/sub2-subscription-confirm.png'), full_page=True)
        await dialog.locator('[data-cancel]').click()
        await expect(push).to_be_enabled()
        assert not writes
        for i in (1, 2, 3, 4):
            await expect(page.locator(f'[data-member="{i}"] .extm-rowck')).to_be_checked()

        # Escape cancels, too; returning to push asks again.
        await push.click(); await page.keyboard.press('Escape')
        await expect(dialog).to_have_count(0); assert not writes
        await push.click()
        await dialog.locator('[data-confirm]').click()
        await expect(push).to_be_enabled()
        assert writes == [('/api/external/members/push-sub2', {'ids': [1, 2, 3, 4]})]
        writes.clear()

        # Polling can reveal another abnormal account during confirmation.
        await select([1, 2]); await push.click()
        rows[0].update(subscription_ok=False)
        await expect(page.locator('[data-member="1"] [data-subscription]')).to_have_text('掉订阅', timeout=10000)
        await dialog.locator('[data-confirm]').click()
        await expect(dialog).to_contain_text('其中 2 个订阅异常或状态未知')
        assert not writes
        await dialog.locator('[data-cancel]').click()

        # Relinking includes both subscription and account-recreation warnings.
        await select([2]); await page.locator('#extm-more-actions > summary').click()
        await page.locator('#extm-sub2-relink').click()
        await expect(dialog).to_contain_text('重新关联')
        await expect(dialog).to_contain_text('恢复其他管理员已删除的账号')
        await dialog.locator('[data-cancel]').click(); assert not writes
        await page.locator('#extm-more-actions > summary').click()
        await page.locator('#extm-sub2-relink').click()
        await dialog.locator('[data-confirm]').click()
        await expect(push).to_be_enabled()
        assert writes == [('/api/external/members/relink-sub2', {'ids': [2]})]
        writes.clear()

        # Navigating away closes the pending confirmation without a write.
        await push.click()
        await page.evaluate("history.pushState({}, '', window.location.pathname.replace('/external-members', '/settings')); window.dispatchEvent(new PopStateEvent('popstate'))")
        await expect(dialog).to_have_count(0)
        assert not writes and not errors, (writes, errors)
        await browser.close()
    print('PASS: normal/abnormal/mixed selection, cancel/Escape, explicit consent, fresh warnings, relink, safe text and navigation')


if __name__ == '__main__':
    asyncio.run(main())
