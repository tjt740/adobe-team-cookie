"""Supply settings placement, shared credentials and async failures, using synthetic APIs."""
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

FRONTEND = Path(__file__).resolve().parents[1]
OUTPUT = FRONTEND.parents[1] / '.local' / 'supply-settings-preview'
ORIGIN = 'http://supply-settings.test'
CARD = '#okad-supply-mail-settings'


async def scenario(browser, prefix, mobile):
    state = dict(configured=False, token='', health='untested', read_error=True,
                 save_error=False, test_error=False, delay_save=False)
    writes, tests, errors, escaped = [], [], [], []
    save_gate = asyncio.Event()
    context = await browser.new_context(viewport={'width':390 if mobile else 1440, 'height':1000},
                                        is_mobile=mobile, has_touch=mobile)

    def config():
        return dict(configured=state['configured'], token=state['token'], health=dict(status=state['health']))

    async def serve(route):
        request = route.request
        path = urlparse(request.url).path
        if prefix and not path.startswith(prefix + '/'):
            escaped.append(path)
            await route.abort()
            return
        path = path[len(prefix):]
        if path.startswith('/api/'):
            status, data = 200, dict(items=[], accounts=[], total=0, ok=True)
            if path == '/api/auth/me':
                data = dict(id=1, username='admin', is_active=True, is_superuser=True)
            elif path == '/api/settings':
                data = dict(concurrency=2, proxy_enabled=False, proxy_url='')
            elif path == '/api/settings/clash':
                data = dict(available=False)
            elif path in ('/api/adobe-accounts/jobs', '/api/admin/users'):
                data = []
            elif path == '/api/external/mail/config':
                assert request.headers['authorization'] == 'Bearer synthetic-supply-settings'
                if request.method == 'PUT':
                    payload = request.post_data_json
                    writes.append(payload)
                    if state['delay_save']:
                        await save_gate.wait()
                    if state['save_error']:
                        status, data = 400, dict(detail='Token 格式无效，请粘贴 Token 裸串')
                    else:
                        state['configured'] = not payload.get('clear_token') and bool(payload.get('token'))
                        state['token'] = payload.get('token', '') if state['configured'] else ''
                        state['health'] = 'untested'
                        data = config()
                elif state['read_error']:
                    state['read_error'] = False
                    status, data = 503, dict(detail='暂时无法读取邮件配置')
                else:
                    data = config()
            elif path == '/api/external/mail/test':
                tests.append(request.method)
                assert state['configured'], 'tested without a saved Token'
                if state['test_error']:
                    state['health'] = 'error'
                    status, data = 400, dict(detail='supply.ink Token 已失效 <img src=x>')
                else:
                    state['health'] = 'ok'
                    data = dict(ok=True, total=21, health=dict(status='ok'))
            await route.fulfill(status=status, json=data)
            return
        file = FRONTEND / path.lstrip('/')
        if not file.is_file():
            file = FRONTEND / ('index-okad.html' if prefix else 'index.html')
        # Patches must wait for the real SPA instead of mounting beside the app shell.
        if file.name == 'index-CrrzYg-U.js':
            await asyncio.sleep(.3)
        await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])

    await context.route('**/*', serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-supply-settings')")
    page = await context.new_page()
    await page.clock.install()
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto(ORIGIN + prefix + '/settings')
    card = page.locator(CARD)
    field = card.locator('#sm-token')
    save = card.locator('.sm-save')
    test = card.get_by_role('button', name='测试连接')
    clear = card.get_by_role('button', name='清除 Token')
    result = card.locator('.sm-result')
    await expect(card).to_be_visible()
    await expect(card.locator('.sm-state')).to_have_text('配置读取失败')
    await expect(result).to_have_text('暂时无法读取邮件配置')
    assert await card.evaluate("el => el.nextElementSibling.id === 'okad-clash-settings'")
    assert await card.evaluate("el => !!el.closest('#app .n-layout-content.content')")
    await expect(page.locator('.ws-settings-nav button').first).to_have_text('Supply 邮件')
    await card.get_by_role('button', name='重新加载').click()
    await expect(card.locator('.sm-state')).to_have_text('未配置')
    await expect(field).to_be_visible()
    await expect(field).to_have_attribute('type', 'text')
    await expect(card).to_have_attribute('data-health', 'neutral')
    await expect(card.locator('.sm-watermark')).to_be_hidden()
    await expect(card.locator('p')).to_have_count(0)
    await expect(test).to_be_disabled()
    await expect(clear).to_be_disabled()
    await save.click()
    await expect(result).to_contain_text('请先粘贴')
    assert not writes

    state['delay_save'] = True
    await field.fill('synthetic-supply-token')
    await save.click()
    await expect(save).to_have_text('保存中…')
    await expect(field).to_be_disabled()
    await expect(test).to_be_disabled()
    await expect(clear).to_be_disabled()
    await expect(card).to_have_attribute('aria-busy', 'true')
    save_gate.set()
    state['delay_save'] = False
    await expect(card.locator('.sm-state')).to_have_text('已配置')
    await expect(field).to_have_value('synthetic-supply-token')
    await expect(card).to_have_attribute('data-health', 'neutral')
    await expect(save).to_have_text('更新 Token')
    await test.click()
    await expect(card).to_have_attribute('data-health', 'ok')
    await expect(card.locator('.sm-watermark')).to_have_text('token 正常')
    await expect(card.locator('[data-sm-status="ok"] svg[data-okad-icon="check"]')).to_be_visible()
    await expect(card.locator('[data-sm-status="error"]')).to_be_hidden()
    assert writes == [{'token':'synthetic-supply-token'}] and tests == ['POST']

    state['save_error'] = True
    await field.fill('replacement-supply-token')
    await expect(card).to_have_attribute('data-health', 'neutral')
    await expect(test).to_be_disabled()
    await save.click()
    await expect(result).to_contain_text('Token 格式无效')
    await expect(field).to_have_value('replacement-supply-token')
    await expect(save).to_be_enabled()
    await expect(card.locator('.sm-state')).to_have_text('已配置')
    state['save_error'] = False
    await save.click()
    await expect(result).to_have_text('已更新')
    await expect(field).to_have_value('replacement-supply-token')
    state['test_error'] = True
    await test.click()
    await expect(result).to_have_text('supply.ink Token 已失效 <img src=x>')
    await expect(result.locator('img')).to_have_count(0)
    await expect(test).to_be_enabled()
    await expect(card).to_have_attribute('data-health', 'error')
    await expect(card.locator('.sm-watermark')).to_have_text('token 异常')
    await expect(card.locator('[data-sm-status="error"] svg[data-okad-icon="error"]')).to_be_visible()
    await expect(card.locator('[data-sm-status="ok"]')).to_be_hidden()
    await page.reload()
    await expect(field).to_have_value('replacement-supply-token')
    await expect(card).to_have_attribute('data-health', 'error')
    state['test_error'] = False
    await clear.click()
    await expect(card.locator('.sm-state')).to_have_text('未配置')
    await expect(test).to_be_disabled()
    await expect(card).to_have_attribute('data-health', 'neutral')
    await expect(field).to_have_value('')
    await expect(card.locator('.sm-watermark')).to_be_hidden()
    assert writes[-1] == {'clear_token':True}
    await field.fill('shared-supply-token')
    await save.click()
    await expect(result).to_have_text('已保存')

    # The external import uses the very same saved configuration.
    if mobile:
        await page.locator('#okad-mobile-menu').click()
    await page.locator('#extm-nav').click()
    await expect(page.locator('#extm-embed')).to_be_visible()
    await expect(card).not_to_be_visible()
    await expect(page.locator('#extm-mail-state')).to_have_text('已配置')
    settings = page.locator('.n-menu-item').filter(has=page.locator(f'a[href="{prefix}/settings"]'))
    if mobile:
        await page.locator('#okad-mobile-menu').click()
    await settings.click()
    await expect(card).to_have_count(1)
    await expect(card.locator('.sm-state')).to_have_text('已配置')
    await expect(field).to_have_value('shared-supply-token')
    await page.reload()
    await expect(card.locator('.sm-state')).to_have_text('已配置')
    await expect(field).to_have_value('shared-supply-token')
    await expect(card).to_have_attribute('data-health', 'neutral')
    assert await card.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    name = ('mobile' if mobile else 'desktop') + ('-okad' if prefix else '')
    await page.screenshot(path=str(OUTPUT / (name + '-neutral.png')))
    await test.click()
    await expect(card).to_have_attribute('data-health', 'ok')
    green = await card.evaluate('el => getComputedStyle(el).backgroundColor')
    # The backend performs hourly checks; polling picks up the new result without a reload.
    state['health'] = 'error'
    await page.clock.fast_forward(60_000)
    await expect(card).to_have_attribute('data-health', 'error')
    await expect(card.locator('.sm-watermark')).to_have_text('token 异常')
    assert await card.evaluate('el => getComputedStyle(el).backgroundColor') != green
    await page.screenshot(path=str(OUTPUT / (name + '-error.png')))
    # A background status refresh must preserve an unsaved edit and keep it neutral.
    await field.fill('unsaved-token')
    state['health'] = 'ok'
    await page.clock.fast_forward(60_000)
    await expect(field).to_have_value('unsaved-token')
    await expect(card).to_have_attribute('data-health', 'neutral')
    await field.fill('shared-supply-token')
    await expect(card).to_have_attribute('data-health', 'ok')
    await expect(card.locator('.sm-watermark')).to_have_text('token 正常')
    await page.screenshot(path=str(OUTPUT / (name + '.png')))
    light = await card.evaluate('el => getComputedStyle(el).backgroundColor')
    await page.evaluate("document.documentElement.classList.add('dark')")
    assert await card.evaluate('el => getComputedStyle(el).backgroundColor') != light
    await page.screenshot(path=str(OUTPUT / (name + '-dark.png')))
    assert not escaped, escaped
    assert not errors, errors
    await context.close()
    print(f'PASS {prefix or "/"} {name}: plaintext Token, neutral/green/red frames, watermarks, polling and remount', flush=True)


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            for prefix in ['', '/okad']:
                for mobile in [False, True]:
                    await scenario(browser, prefix, mobile)
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
