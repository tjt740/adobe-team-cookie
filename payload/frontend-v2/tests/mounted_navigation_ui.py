"""Exercise actual frontend routing at / and /okad with isolated API fixtures."""
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

FRONTEND = Path(__file__).resolve().parents[1]
ORIGIN = "http://okad.test"
PAGES = [
    ("external-members", "#extm-embed"), ("dashboard", ".dash"),
    ("adobe", "#adobe-workspace"), ("pool", "#pool-workspace"),
    ("jobs", "#jobs-workspace"), ("email", "#email-workspace"),
    ("logs", "#logs-workspace"), ("settings", "#ws-settings-heading"),
    ("sub2", "#sub2-panel"),
]


async def check(browser, prefix):
    context = await browser.new_context(viewport={"width": 1440, "height": 1000})
    errors, escaped = [], []

    async def serve(route):
        path = urlparse(route.request.url).path
        if prefix and not path.startswith(prefix + "/"):
            escaped.append(path)
            await route.abort()
            return
        path = path[len(prefix):]
        if path.startswith("/api/"):
            data = dict(items=[], accounts=[], total=0, page=1, size=200, ok=True)
            if path == "/api/auth/me":
                data = dict(id=1, username="admin", is_active=True, is_superuser=True)
            elif path == "/api/settings":
                data = dict(concurrency=2)
            elif path in ("/api/adobe-accounts/jobs", "/api/admin/users"):
                data = []
            elif path == "/api/dashboard/overview":
                data = dict(admins=dict(valid=0, total=0, type2e=0, dead_org=0),
                            members=dict(full4000=0, building=0, zero=0, cookie=0),
                            capacity=dict(deficit=0, healthy=0, ceiling=0),
                            sub2=dict(ok=True, pending=0, live=0, concurrency=0),
                            emails=dict(unused=0, total=0))
            await route.fulfill(json=data)
            return
        file = FRONTEND / path.lstrip("/")
        if not file.is_file():
            file = FRONTEND / ("index-okad.html" if prefix else "index.html")
        await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])

    await context.route("**/*", serve)
    await context.add_init_script("localStorage.setItem('okad_token', 'synthetic-navigation-test')")
    page = await context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.goto(ORIGIN + prefix + "/dashboard")
    for hit in ("label", "icon", "padding"):
        for name, content in PAGES:
            href = prefix + "/" + name
            item = page.locator(".n-menu-item").filter(has=page.locator(f'a[href="{href}"]'))
            if hit == "label":
                await item.locator("a").click()
            elif hit == "icon":
                bounds = await item.locator(".n-menu-item-content__icon").bounding_box()
                await page.mouse.click(bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
            else:
                await item.click(position={"x": 5, "y": 20})
            await expect(page).to_have_url(ORIGIN + href)
            await expect(page.locator(content)).to_be_visible()
            await expect(page.locator(".okad-current-item a")).to_have_attribute("href", href)
            await expect(page.locator(".okad-current-item")).to_have_count(1)
            await expect(page.locator("body")).to_have_attribute("data-workspace", name)
    for name, content in PAGES:
        await page.goto(ORIGIN + prefix + "/" + name + "?source=bookmark#saved")
        await page.reload()
        await expect(page.locator(content)).to_be_visible()
        await expect(page).to_have_url(ORIGIN + prefix + "/" + name + "?source=bookmark#saved")
    # Browser history and keyboard activation must use the same mounted paths.
    await page.locator("#extm-nav").press("Enter")
    await expect(page).to_have_url(ORIGIN + prefix + "/external-members")
    await page.go_back()
    await expect(page.locator("#sub2-panel")).to_be_visible()
    await page.go_forward()
    await expect(page.locator("#extm-embed")).to_be_visible()
    # Settings guards and links inside native screens also need the route base.
    await page.goto(ORIGIN + prefix + "/settings")
    for selector in ("#okad-supply-mail-settings", "#okad-clash-settings", "#okad-local-pool-settings", "#okad-external-apikey",
                     "#okad-captcha-settings", "#okad-user-management"):
        await expect(page.locator(selector)).to_be_visible()
    await page.goto(ORIGIN + prefix + "/logs")
    await page.get_by_role("button", name="任务中心 →").click()
    await expect(page).to_have_url(ORIGIN + prefix + "/jobs")
    # Native new-tab navigation uses each custom anchor's real href.
    href = await page.locator("#extm-nav a").get_attribute("href")
    other = await context.new_page()
    await other.goto(ORIGIN + href)
    await expect(other.locator("#extm-embed")).to_be_visible()
    assert not errors, errors
    assert not escaped, escaped
    await context.close()
    print(f"PASS {prefix or '/'}: nine menus, hit targets, selection, reload, history, settings and internal links", flush=True)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            await check(browser, "/okad")
            await check(browser, "")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
