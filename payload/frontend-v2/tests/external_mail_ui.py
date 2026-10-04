"""账号密码导入、邮件 Token 与正文查看的浏览器回归；API 全部使用合成数据。"""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get("ADOBE_TEST_URL", "http://127.0.0.1:18080")
ROOT = Path(__file__).resolve().parents[3]


async def main():
    configured = False
    state = {"import_error": False, "mail_error": False, "mail_reads": 0}
    imports = []
    pushes = []
    row = dict(id=1, email="one@example.com", login_status="ok", has_cookie=True,
               has_adobe_password=True, subscription_ok=True, created_at="2026-10-05T00:00:00Z")

    async def api(route):
        nonlocal configured
        request = route.request
        path = urlparse(request.url).path
        status = 200
        if path == "/api/auth/me":
            data = dict(id=1, username="admin", is_superuser=True, is_active=True)
        elif path == "/api/external/members":
            data = dict(items=[row], total=1)
        elif path == "/api/external/mail/config":
            if request.method == "PUT":
                payload = request.post_data_json
                configured = not payload.get("clear_token") and bool(payload.get("token"))
            data = dict(configured=configured)
        elif path == "/api/external/mail/test":
            if configured:
                data = dict(ok=True, total=21, message="supply.ink 邮件连接成功")
            else:
                status, data = 400, dict(detail="请先保存 supply.ink Token")
        elif path == "/api/external/members/1/mail":
            state["mail_reads"] += 1
            if state["mail_error"]:
                status, data = 400, dict(detail="supply.ink Token 已失效")
            else:
                data = dict(email=row["email"], messages=[dict(subject="Adobe 验证码", date="2026-10-05T04:00:00Z",
                                                             body="Your code is 654321\n<img src=x onerror=alert(1)>")])
        elif path == "/api/external/members/import":
            imports.append(request.post_data_json)
            if state["import_error"]:
                data = dict(created=0, updated=0, skipped=0, failed=1, errors=["第 1 行:缺少 Adobe 密码"])
            else:
                data = dict(created=1, updated=0, skipped=0, failed=0, errors=[], job_id=987,
                            sequential_login="----" not in request.post_data_json["content"])
        elif path == "/api/external/members/push-sub2":
            pushes.append(request.post_data_json)
            data = dict(message="已提交 1 个账号同步", queued=1, skipped=0)
        elif path == "/api/external/members/sub2-stock":
            data = dict(ok=True, configured=True, checked_at="2026-10-05T04:00:00Z", items={"1": {"in_stock": False}})
        elif path == "/api/adobe-accounts/jobs":
            data = []
        else:
            data = dict(items=[], total=0)
        await route.fulfill(status=status, json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.route("**/api/**", api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + "/external-members")
        await expect(page.locator("#extm-mail-state")).to_have_text("未配置")
        await expect(page.locator("#extm-mail-config")).to_be_hidden()
        await page.locator("#extm-otp-mode").select_option("auto")
        await expect(page.locator("#extm-mail-config")).to_be_visible()
        await page.locator("#extm-mail-config > summary").click()
        await page.locator("#extm-mail-token").fill("test-supply-token")
        await page.locator("#extm-mail-save").click()
        await expect(page.locator("#extm-mail-state")).to_have_text("已配置")
        await expect(page.locator("#extm-mail-token")).to_have_value("")
        await page.locator("#extm-mail-test").click()
        await expect(page.locator("#extm-mail-result")).to_contain_text("21 个账号")
        await page.locator("#extm-otp-mode").select_option("manual")
        await expect(page.locator("#extm-mail-config")).to_be_hidden()
        await expect(page.locator("#extm-mail-config")).not_to_have_attribute("open", "")
        await expect(page.locator("#extm-mail-state")).to_have_text("已配置")
        await page.locator("#extm-otp-mode").select_option("")
        await expect(page.locator("#extm-mail-config")).to_be_hidden()
        await page.locator("#extm-import").fill("one@example.com----Known9!")
        await page.locator("#extm-do-import").click()
        await expect(page.locator("#extm-op")).to_contain_text("登录任务 #987")
        assert imports == [dict(content="one@example.com----Known9!", on_duplicate="skip")]
        await expect(page.locator("#extm-import")).to_have_value("")
        await expect(page.get_by_text("按粘贴顺序逐个获取验证码登录", exact=False)).to_be_visible()
        await page.locator("#extm-import").fill("one@example.com\ntwo@example.com")
        await page.locator("#extm-do-import").click()
        await expect(page.locator("#extm-op")).to_contain_text("登录任务 #987")
        assert imports[-1] == dict(content="one@example.com\ntwo@example.com", on_duplicate="skip")
        await expect(page.locator("#extm-op")).to_contain_text("按导入顺序逐个自动取码登录")
        await expect(page.locator("#extm-import")).to_have_value("")
        state["import_error"] = True
        await page.locator("#extm-import").fill("one@example.com----")
        await page.locator("#extm-do-import").click()
        await expect(page.locator("#extm-op")).to_contain_text("缺少 Adobe 密码")
        await expect(page.locator("#extm-import")).to_have_value("one@example.com----")
        await page.locator("[data-mail='1']").click()
        dialog = page.locator("#extm-mail-dialog")
        await expect(dialog.locator("summary")).to_contain_text("Adobe 验证码")
        await dialog.locator("summary").click()
        await expect(dialog.locator("pre")).to_contain_text("654321")
        assert await dialog.locator("img").count() == 0
        state["mail_error"] = True
        await dialog.locator("[data-refresh]").click()
        await expect(dialog.locator("[data-messages]")).to_contain_text("Token 已失效")
        await expect(dialog.locator("[data-refresh]")).to_be_enabled()
        await dialog.locator("[data-close]").click()
        await expect(dialog).to_have_count(0)
        await page.locator("[data-member='1'] .extm-rowck").check()
        await page.locator("#extm-sub2-push").click()
        await expect(page.locator("#extm-op")).to_contain_text("已提交 1 个账号同步")
        assert pushes == [{"ids": [1]}]
        await page.locator("#extm-otp-mode").select_option("auto")
        await page.locator("#extm-mail-config > summary").click()
        await page.locator("#extm-mail-clear").click()
        await expect(page.locator("#extm-mail-state")).to_have_text("未配置")
        await page.locator("#extm-mail-test").click()
        await expect(page.locator("#extm-mail-result")).to_contain_text("请先保存")
        await page.locator("#extm-import").fill("")
        await page.locator("#extm-mail-token").fill("test-supply-token")
        await page.locator("#extm-mail-save").click()
        await expect(page.locator("#extm-mail-state")).to_have_text("已配置")
        (ROOT / ".local").mkdir(exist_ok=True)
        await page.screenshot(path=str(ROOT / ".local/external-mail-ui.png"), full_page=True)
        assert not errors, errors
        await browser.close()
        print("External mail UI passed: config, email-only/password import, error retention, safe mail body and Sub2 push")


asyncio.run(main())
