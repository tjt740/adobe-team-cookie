"""Login sync must appear without reloading, even with slow details and cached stock."""
import asyncio
import copy
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

FRONT = Path(os.environ.get('OKAD_FRONTEND_DIR', Path(__file__).resolve().parents[1]))


async def scenario(browser, prefix, expand):
    row = dict(id=1, email='login-sync@example.test', login_status='never',
               has_cookie=False, credits_total=None, sub2_status='not_pushed')
    job = dict(id=90, type='external_login', status='running', target=1,
               success=0, fail=0, logs=[], log_total=0, extra={})
    detail_entered, release_detail = asyncio.Event(), asyncio.Event()
    stock_entered, release_stock = asyncio.Event(), asyncio.Event()
    remote_stock, cached_stock = False, False
    hold_stock = False
    writes, errors, forced_stock = [], [], []

    async def serve(route):
        nonlocal cached_stock
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix(prefix)
        if not path.startswith('/api/'):
            file = FRONT / path.lstrip('/')
            if not file.is_file():
                file = FRONT / ('index-okad.html' if prefix else 'index.html')
            return await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])
        if request.method != 'GET':
            writes.append((path, request.post_data_json))
            assert path == '/api/external/members/batch-login'
            row['latest_job'] = {**job, 'item_status': 'running'}
            data = job
        elif path == '/api/auth/me':
            data = dict(id=1, username='admin', is_active=True, is_superuser=True)
        elif path == '/api/external/members':
            data = dict(items=[copy.deepcopy(row)], total=1)
        elif path == '/api/external/members/1/jobs':
            detail_entered.set()
            await release_detail.wait()
            data = [job]
        elif path == '/api/adobe-accounts/jobs/90':
            data = job
        elif path == '/api/external/members/sub2-stock':
            # Model the server cache: an ordinary poll retains the previous
            # inventory. A forced read must follow the successful delivery.
            if hold_stock:
                stock_entered.set()
                await release_stock.wait()
            if parse_qs(url.query).get('refresh') == ['true']:
                cached_stock = remote_stock
                forced_stock.append(cached_stock)
            data = dict(ok=True, configured=True, checked_at='2026-10-19T01:00:00Z',
                        items={1: dict(email=row['email'], in_stock=cached_stock,
                                       account_ids=[1123] if cached_stock else [])})
        elif path == '/api/adobe-accounts/jobs':
            data = []
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    page = await browser.new_page(viewport={'width': 1600, 'height': 1000},
                                  timezone_id='Asia/Shanghai')
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.route('**/*', serve)
    await page.add_init_script("localStorage.setItem('okad_token','synthetic-sync-polling')")
    try:
        await page.goto('http://login-sync.test' + prefix + '/external-members')
        member = page.locator('tr[data-member="1"]')
        stock = member.locator('[data-sub2-stock]')
        timestamp = member.locator('[data-sub2-pushed-at]')
        await expect(stock).to_have_text('未在库 Sub2')
        if expand:
            await member.locator('[data-login]').click()
            await asyncio.wait_for(detail_entered.wait(), 5)
        else:
            await member.locator('.extm-rowck').check()
            await page.locator('#extm-batch-login').click()
        row.update(login_status='ok', has_cookie=True, subscription_ok=True,
                   credits_total=4000, credits_available=4000,
                   sub2_status='pending', sub2_message='等待同步 Cookie')
        await expect(member).to_contain_text('Sub2 待同步', timeout=6000)
        await expect(timestamp).to_have_text('—')

        # Keep an old inventory request in flight across the delivery. Its
        # completion must not swallow the forced follow-up read.
        hold_stock = True
        await asyncio.wait_for(stock_entered.wait(), 6)
        remote_stock = True
        job.update(status='done', success=1)
        row.update(sub2_status='synced', sub2_account_id=1123,
                   sub2_synced_at='2026-10-19T01:00:05Z',
                   latest_job={**job, 'item_status': 'done', 'item_message': '登录成功'})
        await expect(timestamp).to_have_text('2026-10-19 09:00:05', timeout=6500)
        hold_stock = False
        release_stock.set()
        await expect(stock).to_have_text('在库 Sub2', timeout=6000)
        await expect(member).not_to_contain_text('Sub2 待同步')
        assert True in forced_stock
        assert writes == [('/api/external/members/batch-login', {'ids': [1]})], writes
        if expand:
            assert not release_detail.is_set(), 'List refresh must not wait for task details'
        # Stable receipts must not keep bypassing the inventory cache.
        reads = len(forced_stock)
        await page.wait_for_timeout(6500)
        assert len(forced_stock) == reads, forced_stock

        # Restoring a hidden tab refreshes both saved sync state and inventory.
        await page.evaluate('''() => {
          window.testHidden = true;
          Object.defineProperty(document, 'hidden', {configurable:true, get:() => window.testHidden});
          document.dispatchEvent(new Event('visibilitychange'));
        }''')
        row.update(sub2_status='failed', sub2_message='模拟同步失败')
        await page.wait_for_timeout(3200)
        await expect(member).not_to_contain_text('模拟同步失败')
        await page.evaluate('''() => {
          window.testHidden = false;
          document.dispatchEvent(new Event('visibilitychange'));
        }''')
        await expect(member).to_contain_text('模拟同步失败', timeout=2000)
        await expect(timestamp).to_have_text('2026-10-19 09:00:05')
        assert not errors, errors
    finally:
        release_detail.set()
        release_stock.set()
        await page.close()


async def main():
    async with async_playwright() as playwright:
        browser = await getattr(playwright, os.environ.get('POLLING_BROWSER', 'chromium')).launch()
        try:
            for prefix in ('', '/okad'):
                for expand in (False, True):
                    await scenario(browser, prefix, expand)
        finally:
            await browser.close()
    print('PASS: automatic login sync, slow details, cached/in-flight inventory, stable receipts and tab resume; root and /okad')


if __name__ == '__main__':
    asyncio.run(main())
