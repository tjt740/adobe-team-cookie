"""Per-account login phases while a 50-account batch remains active."""
import asyncio
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

FRONT = Path(os.environ.get('OKAD_FRONTEND_DIR', Path(__file__).resolve().parents[1]))


async def main():
    job = dict(id=90, type='external_login', status='running', target=105, success=1, fail=1,
               created_at=1791680000, logs=[], log_total=0, extra={'batch': {'index': 1, 'total': 3, 'size': 50}})
    phases = ['pending', 'running', 'done', 'failed', 'interrupted']
    rows = [dict(id=i, email=f'batch{i}@example.test', login_status='ok', has_cookie=True,
                 created_at='2026-10-10T00:00:00', subscription_ok=True,
                 latest_job={**job, 'item_status': phase, 'item_message': '本轮结果',
                             'status': 'error' if phase == 'interrupted' else 'running'})
            for i, phase in enumerate(phases, 1)]
    async def serve(route):
        path = urlparse(route.request.url).path.removeprefix('/okad')
        if path.startswith('/api/'):
            if path == '/api/auth/me':
                data = dict(id=1, username='admin', is_active=True, is_superuser=True)
            elif path == '/api/external/members':
                data = dict(items=rows, total=len(rows))
            elif path.endswith('/jobs'):
                data = [job]
            elif path == '/api/adobe-accounts/jobs/90':
                data = job
            else:
                data = dict(items=[], total=0)
            await route.fulfill(json=data)
        else:
            file = FRONT / path.lstrip('/')
            if not file.is_file():
                file = FRONT / 'index-okad.html'
            await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/*', serve)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-batch-test')")
        await page.goto('http://okad.test/okad/external-members')
        for mid, label in enumerate(['排队中', '登录中', '本轮成功', '本轮失败', '已中断'], 1):
            row = page.locator(f'tr[data-member="{mid}"]')
            await expect(row.locator('.extm-status')).to_contain_text(label)
            button = row.locator('[data-login]')
            await expect(button).to_have_attribute('aria-busy', 'true' if mid == 2 else 'false')
            await expect(button.locator('.extm-spin')).to_have_count(1 if mid == 2 else 0)
            if mid == 5:
                await expect(button).to_be_enabled()
            else:
                await expect(button).to_be_disabled()
        await page.locator('[data-member="3"] .extm-toggle').click()
        await expect(page.locator('[data-login-batch]')).to_have_text('批次 1/3 · 每批最多 50 个')
        await page.locator('[data-action="refresh"]').click()
        await page.locator('[data-action="refresh"]').click()
        await expect(page.locator('[data-login-batch]')).to_have_count(1)
        await expect(page.locator('#extm-import-drawer')).to_contain_text('登录成功后自动推送 Sub2')
        assert not errors, errors
        await browser.close()
        print('PASS: queued/running/success/failure/interrupted rows, spinner accuracy and batch progress')


asyncio.run(main())
