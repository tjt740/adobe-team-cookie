"""越南登录的显式选择、批量粘贴、草稿与重登设置；所有请求使用本地合成数据。"""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect
from external_controls import select_value, expect_select
from mobile_workspace_ui import Fixtures, fits, dialog_fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'vietnam-login-preview'


class VietnamFixtures(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.rows[0].update(otp_mode='vietnam', has_adobe_password=True, uses_supply_mail=False)
        self.rows[2].update(otp_mode='auto', has_adobe_password=True, uses_supply_mail=True)

    async def serve(self, route):
        url = urlparse(route.request.url)
        if url.netloc != 'vietnam.test':
            self.escaped.append(route.request.url)
            return await route.abort()
        path = url.path.removeprefix(self.prefix)
        if path == '/api/external/members/import':
            self.writes.append((path, route.request.post_data_json))
            return await route.fulfill(json=dict(created=2, updated=0, skipped=0, failed=0, errors=[], job_id=987, sequential_login=True))
        if path.endswith('/otp-mode'):
            payload = route.request.post_data_json
            self.writes.append((path, payload))
            row = next(r for r in self.rows if r['id'] == int(path.split('/')[-2]))
            row.update(otp_mode=payload['otp_mode'], uses_supply_mail=payload['otp_mode'] == 'auto')
            return await route.fulfill(json=dict(otp_mode=row['otp_mode'], message='取码方式已保存，下次登录生效'))
        return await super().serve(route)


async def check(browser, prefix, width):
    context = await browser.new_context(viewport=dict(width=width, height=950), locale='zh-CN')
    fixtures, errors = VietnamFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-vietnam-ui')")
    page = await context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto('http://vietnam.test' + prefix + '/external-members')
    await expect(page.locator('[data-otp-settings="1"]')).to_have_text('越南登录')
    await expect(page.locator('[data-member="1"] .extm-company-tag')).to_have_count(0)
    await expect(page.locator('[data-otp-settings="3"]')).to_have_text('自动取码')
    await page.locator('#extm-open-import').click()
    await expect_select(page, '#extm-otp-mode', '')
    await select_value(page, '#extm-otp-mode', 'vietnam')
    await expect(page.locator('#extm-mail-config')).not_to_be_visible()
    await expect(page.locator('#extm-import-drawer')).to_contain_text('越南登录需填写邮箱和 Adobe 密码')
    content = 'synthetic1@example.com\tTest&9@*c@!$\nsynthetic2@example.com\tTest#8%$!@'
    await page.locator('#extm-import').fill(content)
    await page.locator('#extm-import-done').click()
    await page.locator('#extm-open-import').click()
    await expect_select(page, '#extm-otp-mode', 'vietnam')
    await expect(page.locator('#extm-import')).to_have_value(content)
    await dialog_fits(page, '#extm-import-drawer')
    await page.screenshot(path=str(OUTPUT / f'import-{prefix.strip("/") or "root"}-{width}.png'))
    await page.locator('#extm-do-import').click()
    await expect(page.locator('#extm-import-result')).to_contain_text('登录任务 #987')
    await expect(page.locator('#extm-import-result')).to_contain_text('逐个自动取码登录')
    await expect(page.locator('#extm-import')).to_have_value('')
    assert fixtures.writes == [('/api/external/members/import', dict(content=content, on_duplicate='skip', otp_mode='vietnam'))]
    await page.locator('#extm-import-done').click()
    await page.locator('[data-otp-settings="3"]').click()
    await page.locator('[data-otp-mode="3"]').select_option('vietnam')
    await dialog_fits(page, '#extm-mode-dialog')
    await page.locator('#extm-mode-dialog [type=submit]').click()
    await expect(page.locator('#extm-mode-dialog')).to_have_count(0)
    await expect(page.locator('[data-otp-settings="3"]')).to_have_text('越南登录')
    await expect(page.locator('[data-member="3"] .extm-company-tag')).to_have_count(0)
    assert fixtures.writes[-1] == ('/api/external/members/3/otp-mode', {'otp_mode': 'vietnam'})
    await page.reload()
    await expect(page.locator('[data-otp-settings="3"]')).to_have_text('越南登录')
    assert not fixtures.escaped, fixtures.escaped
    assert not errors, errors
    await fits(page, '#extm-embed')
    await context.close()


async def main():
    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('VIETNAM_BROWSER', 'chromium')).launch()
        for prefix in ('', '/okad'):
            for width in (1440, 390):
                await check(browser, prefix, width)
        await browser.close()
    print('PASS: Vietnam selection, batch paste, payload, draft, saved account mode, tags and same-origin requests on desktop/mobile on both routes')


if __name__ == '__main__':
    asyncio.run(main())
