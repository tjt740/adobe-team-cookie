"""Title reveal control with synthetic credentials, covering login and authenticated pages."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get("ADOBE_TEST_URL", "http://127.0.0.1:18080")
ROOT = Path(__file__).resolve().parents[3]


async def main():
    reads = 0
    deny = False

    async def api(route):
        nonlocal reads
        path = urlparse(route.request.url).path
        if path == "/api/auth/login-hints":
            reads += 1
            if deny:
                await route.fulfill(status=401, json={"detail": "请先登录管理员账号后查看登录密码"})
                return
            data = {"entries": [
                dict(label="本地", url=BASE, username="admin", password="Local9!"),
                dict(label="线上", url="https://online.example.com", username="admin", password="Online9!"),
            ]}
        elif path == "/api/auth/me":
            data = dict(id=1, username="admin", is_superuser=True, is_active=True)
        elif path == "/api/adobe-accounts/jobs":
            data = []
        else:
            data = dict(items=[], total=0)
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.route("**/api/**", api)
        await page.goto(BASE + "/login")
        button = page.get_by_role("button", name="查看本地和线上登录密码")
        await expect(button).to_have_attribute("aria-expanded", "false")
        assert reads == 0
        assert "Local9!" not in await page.content()
        await button.click()
        panel = page.locator("#okad-login-hints")
        await expect(panel).to_contain_text("Local9!")
        await expect(panel).to_contain_text("Online9!")
        assert reads == 1
        await page.keyboard.press("Escape")
        await expect(panel).to_have_count(0)
        assert "Online9!" not in await page.content()
        await button.click()
        await expect(panel).to_contain_text("Local9!")
        await button.click()
        await expect(panel).to_have_count(0)
        await page.screenshot(path=str(ROOT / ".local/login-hints-hidden.png"))
        await page.evaluate("localStorage.setItem('okad_token', 'synthetic-ui-token')")
        await page.goto(BASE + "/external-members")
        await expect(button).to_be_visible()
        await button.click()
        await expect(panel).to_contain_text("Online9!")
        box = await button.bounding_box()
        assert box["x"] + box["width"] <= 220, box
        await page.keyboard.press("Escape")
        deny = True
        await button.click()
        await expect(panel).to_contain_text("请先登录管理员")
        assert "Online9!" not in await page.content()
        await page.keyboard.press("Escape")
        await page.reload()
        await expect(button).to_have_attribute("aria-expanded", "false")
        assert not errors, errors
        await browser.close()
        print("PASS: title reveal on login/admin pages, no initial secret fetch, collapse/removal, access denial and refresh default")


asyncio.run(main())
