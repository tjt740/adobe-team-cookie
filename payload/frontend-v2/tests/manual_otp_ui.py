"""手动验证码浏览器回归；使用合成账号与验证码，不连接 Adobe 或邮件服务。"""
import asyncio
import os
from pathlib import Path
import time
from urllib.parse import urlparse

from external_controls import select_value
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("ADOBE_TEST_URL", "http://127.0.0.1:18080")
ROOT = Path(__file__).resolve().parents[3]


async def main():
    rows = [
        dict(id=1, email="company@example.com", otp_mode="auto", uses_supply_mail=True),
        dict(id=2, email="ordinary@example.com", otp_mode="manual", uses_supply_mail=False),
        dict(id=3, email="switch@example.com", otp_mode="auto", uses_supply_mail=True),
    ]
    for row in rows:
        row.update(login_status="never", has_cookie=False, created_at="2026-10-05T00:00:00Z")
    rows[1]["otp_challenge"] = dict(request_id="a"*32, email=rows[1]["email"], expires_at=int(time.time())+120)
    imports, submissions, modes = [], [], []
    state = {"post_error": False}

    async def api(route):
        request = route.request
        path = urlparse(request.url).path
        status = 200
        if path == "/api/auth/me":
            data = dict(id=1, username="admin", is_superuser=True, is_active=True)
        elif path == "/api/external/members":
            data = dict(items=rows, total=len(rows))
        elif path == "/api/external/mail/config":
            data = dict(configured=True)
        elif path.endswith("/otp-mode"):
            payload = request.post_data_json
            modes.append(payload)
            row = rows[int(path.split('/')[-2])-1]
            row["otp_mode"] = payload["otp_mode"]
            row["uses_supply_mail"] = row["otp_mode"] != "manual"
            data = dict(otp_mode=row["otp_mode"], message="取码方式已保存，下次登录生效")
        elif path == "/api/external/members/2/otp":
            if request.method == "POST":
                payload = request.post_data_json
                submissions.append(payload)
                if state["post_error"]:
                    status, data = 409, dict(detail="验证码请求已失效")
                else:
                    assert payload["request_id"] == rows[1]["otp_challenge"]["request_id"]
                    rows[1]["otp_challenge"] = None
                    rows[1].update(login_status="ok", has_cookie=True)
                    data = dict(message="验证码已提交，正在继续登录")
            else:
                data = dict(challenge=rows[1]["otp_challenge"])
        elif path == "/api/external/members/import":
            imports.append(request.post_data_json)
            data = dict(created=1, updated=0, skipped=0, failed=0, errors=[], job_id=987)
        elif path == "/api/external/members/sub2-stock":
            data = dict(ok=False, configured=False, items={})
        elif path == "/api/adobe-accounts/jobs":
            data = []
        else:
            data = dict(items=[], total=0)
        await route.fulfill(status=status, json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1500, "height": 1080})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.route("**/api/**", api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + "/external-members")
        await expect(page.locator('[data-member="1"] .extm-company-tag')).to_have_text("公司")
        await expect(page.locator('[data-member="2"] .extm-company-tag')).to_have_count(0)
        await expect(page.locator('#extm-otp-notice')).to_contain_text("1 个账号等待")
        await expect(page.locator('[data-otp-settings="2"]')).to_be_disabled()
        await page.locator('[data-otp-settings="3"]').click()
        await page.locator('[data-otp-mode="3"]').select_option('manual')
        await page.locator('#extm-mode-dialog [type=submit]').click()
        await expect(page.locator('#extm-mode-dialog')).to_have_count(0)
        await expect(page.locator('[data-otp-settings="3"]')).to_have_text('手动验证码')
        await expect(page.locator('[data-member="3"] .extm-company-tag')).to_have_count(0)
        assert modes == [{"otp_mode": "manual"}]
        await page.locator('#extm-open-import').click()
        await select_value(page, '#extm-otp-mode', 'manual')
        await page.locator('#extm-import').fill('new@example.com')
        await page.locator('#extm-do-import').click()
        await expect(page.locator('#extm-op')).to_contain_text('任务 #987')
        assert imports == [dict(content='new@example.com', on_duplicate='skip', otp_mode='manual')]

        await page.locator('#extm-import-done').click()
        await page.locator('[data-otp="2"]').click()
        dialog = page.locator('#extm-otp-dialog')
        await expect(dialog.locator('p')).to_have_text('ordinary@example.com')
        await expect(dialog.locator('[role=status]')).to_contain_text('剩余')
        await dialog.locator('input').fill('123456')
        await dialog.locator('[data-close]').click()
        await expect(dialog).to_have_count(0)
        assert not submissions and rows[1]['otp_challenge']
        await page.reload()
        await page.locator('[data-otp="2"]').click()
        dialog = page.locator('#extm-otp-dialog')
        await expect(dialog.locator('input')).to_have_value('')
        await dialog.locator('input').fill('654321')
        rows[1]['otp_challenge'] = dict(request_id='b'*32, email=rows[1]['email'], expires_at=int(time.time())+120)
        await expect(dialog.locator('[type=submit]')).to_be_disabled(timeout=6000)
        await expect(dialog.locator('input')).to_have_value('')
        await expect(dialog.locator('[role=alert]')).to_contain_text('请求已结束')
        await dialog.locator('[data-close]').click()

        await page.locator('[data-otp="2"]').click()
        dialog = page.locator('#extm-otp-dialog')
        state['post_error'] = True
        await dialog.locator('input').fill('654321')
        await dialog.locator('[type=submit]').click()
        await expect(dialog.locator('[role=alert]')).to_contain_text('请求已失效')
        await expect(dialog.locator('[type=submit]')).to_be_enabled()
        state['post_error'] = False
        await dialog.locator('[type=submit]').click()
        await expect(dialog).to_have_count(0)
        assert submissions[-1] == dict(request_id='b'*32, code='654321')
        await expect(page.locator('[data-otp="2"]')).to_have_count(0)
        await expect(page.locator('[data-member="2"]')).to_contain_text('登录成功')

        rows[1]['otp_challenge'] = dict(request_id='c'*32, email=rows[1]['email'], expires_at=int(time.time())-1)
        await page.locator('#extm-refresh').click()
        await page.locator('[data-otp="2"]').click()
        dialog = page.locator('#extm-otp-dialog')
        await expect(dialog.locator('[type=submit]')).to_be_disabled()
        await expect(dialog.locator('[role=alert]')).to_contain_text('过期')
        await dialog.locator('[data-close]').click()
        rows[1]['otp_challenge'] = dict(request_id='d'*32, email=rows[1]['email'], expires_at=int(time.time())+120)
        await page.locator('#extm-refresh').click()
        await page.locator('[data-otp="2"]').click()
        await expect(page.locator('#extm-otp-dialog input')).to_have_value('')
        (ROOT / '.local').mkdir(exist_ok=True)
        await page.screenshot(path=str(ROOT / '.local/manual-otp-ui.png'), full_page=True)
        assert not errors, errors
        await browser.close()
        print('Manual OTP UI passed: mode/import, company tag, waiting prompt, refresh, stale request, timeout and submission')


asyncio.run(main())
