"""Multi-token editing, isolated checks and refresh using only synthetic APIs."""
import asyncio
import copy
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

FRONTEND = Path(__file__).resolve().parents[1]
OUTPUT = FRONTEND.parents[1] / '.local/multiple-supply-preview'
ORIGIN = 'http://supply-settings.test'
CARD = '#okad-supply-mail-settings'
SECOND = '2' * 32


async def scenario(browser, prefix, mobile):
    rows = [{'id':'default', 'name':'默认 Token', 'token':'original-supply-token', 'enabled':True,
             'configured':True, 'health':{'status':'ok'}}]
    state = {'read_error':True, 'fail_default':False, 'delay_default':False}
    writes, tests, errors, escaped = [], [], [], []
    gate = asyncio.Event()
    context = await browser.new_context(viewport={'width':390 if mobile else 1440, 'height':1000},
                                        is_mobile=mobile, has_touch=mobile)
    def config():
        return {'configured':any(r['enabled'] and r['token'] for r in rows), 'token':rows[0]['token'],
                'health':copy.deepcopy(rows[0]['health']), 'tokens':copy.deepcopy(rows)}
    async def serve(route):
        request = route.request
        path = urlparse(request.url).path
        if prefix and not path.startswith(prefix + '/'):
            escaped.append(path); await route.abort(); return
        path = path[len(prefix):]
        if path.startswith('/api/'):
            status, data = 200, {'items':[], 'accounts':[], 'total':0, 'ok':True}
            if path == '/api/auth/me':
                data = {'id':1, 'username':'admin', 'is_active':True, 'is_superuser':True}
            elif path == '/api/settings':
                data = {'concurrency':2, 'proxy_enabled':False, 'proxy_url':''}
            elif path == '/api/settings/clash':
                data = {'available':False}
            elif path in ('/api/adobe-accounts/jobs', '/api/admin/users'):
                data = []
            elif path == '/api/external/mail/config':
                if state['read_error']:
                    state['read_error'] = False
                    status, data = 503, {'detail':'暂时无法读取邮件配置'}
                else: data = config()
            elif path.startswith('/api/external/mail/tokens'):
                assert request.headers['authorization'] == 'Bearer synthetic-supply-settings'
                parts = path.split('/')
                identifier = parts[5] if len(parts) > 5 else None
                row = next((r for r in rows if r['id'] == identifier), None)
                if path.endswith('/test'):
                    tests.append(identifier)
                    if identifier == 'default' and state['delay_default']: await gate.wait()
                    if identifier == 'default' and state['fail_default']:
                        row['health'] = {'status':'error'}
                        status, data = 400, {'detail':'supply.ink Token 已失效'}
                    else:
                        row['health'] = {'status':'ok'}
                        data = {'ok':True, 'health':copy.deepcopy(row['health'])}
                else:
                    payload = request.post_data_json if request.method != 'DELETE' else {}
                    writes.append((request.method, identifier, payload))
                    if any(r['id'] != identifier and r['token'] == payload.get('token') for r in rows):
                        status, data = 400, {'detail':'该 Token 已存在，请编辑已有配置'}
                    elif request.method == 'POST':
                        rows.append({'id':SECOND, 'name':payload['name'], 'token':payload['token'],
                                     'enabled':True, 'configured':True, 'health':{'status':'untested'}})
                        data = dict(config(), created_id=SECOND)
                    elif request.method == 'DELETE':
                        rows.remove(row); data = config()
                    else:
                        if ('token' in payload and payload['token'] != row['token']) or 'enabled' in payload or payload.get('clear_token'):
                            row['health'] = {'status':'untested'}
                        row.update({k:v for k,v in payload.items() if k in ('token','name','enabled')})
                        if payload.get('clear_token'): row['token'] = ''
                        row['configured'] = bool(row['token']); data = config()
            await route.fulfill(status=status, json=data); return
        file = FRONTEND / path.lstrip('/')
        if not file.is_file(): file = FRONTEND / ('index-okad.html' if prefix else 'index.html')
        if file.name == 'index-CrrzYg-U.js': await asyncio.sleep(.2)
        await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])
    await context.route('**/*', serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-supply-settings')")
    page = await context.new_page(); await page.clock.install()
    page.on('pageerror', lambda error:errors.append(str(error)))
    await page.goto(ORIGIN + prefix + '/settings')
    root = page.locator(CARD)
    await expect(root.locator('.sm-load-result')).to_have_text('暂时无法读取邮件配置')
    await root.locator('.sm-retry').click()
    default = root.locator('[data-token-id="default"]')
    await expect(default.locator('#sm-token')).to_have_value('original-supply-token')
    await expect(default.locator('#sm-token')).to_have_attribute('type','text')
    await expect(default).to_have_attribute('data-health','ok')
    await expect(default.locator('[data-sm-status="ok"] svg')).to_be_visible()
    assert not writes
    assert await root.evaluate("el=>el.nextElementSibling.id==='okad-clash-settings'")
    await root.locator('.sm-add').click()
    draft = root.locator('[data-token-id^="draft-"]')
    await expect(draft).to_have_attribute('data-health','neutral')
    await draft.locator('[id^="sm-name"]').fill('第二个 Token')
    await draft.locator('[id^="sm-token"]').fill('second-supply-token')
    await expect(draft.locator('.sm-test')).to_be_disabled()
    await draft.locator('.sm-save').click()
    second = root.locator('[data-token-id="'+SECOND+'"]')
    await expect(second.locator('[id^="sm-token"]')).to_have_value('second-supply-token')
    await expect(second).to_have_attribute('data-health','neutral')
    assert rows[0]['token'] == 'original-supply-token' and rows[0]['health']['status'] == 'ok'
    # Checking one row must not disable edits and saves in another row.
    state.update(delay_default=True, fail_default=True)
    await default.locator('.sm-test').click()
    await expect(default.locator('.sm-test')).to_have_text('测试中…')
    await expect(second.locator('.sm-save')).to_be_enabled()
    await second.locator('[id^="sm-name"]').fill('独立保存')
    await second.locator('.sm-save').click()
    await expect(second.locator('h4')).to_have_text('独立保存')
    gate.set()
    await expect(default).to_have_attribute('data-health','error')
    await expect(default.locator('.sm-watermark-label')).to_have_text('token 异常')
    await expect(second).to_have_attribute('data-health','neutral')
    await second.locator('.sm-test').click()
    await expect(second).to_have_attribute('data-health','ok')
    await expect(second.locator('.sm-watermark-label')).to_have_text('token 正常')
    assert tests == ['default',SECOND]
    await second.locator('[id^="sm-token"]').fill('unsaved-edit')
    rows[0]['health'] = {'status':'ok'}
    await page.clock.fast_forward(60_000)
    await expect(default).to_have_attribute('data-health','ok')
    await expect(second.locator('[id^="sm-token"]')).to_have_value('unsaved-edit')
    await expect(second).to_have_attribute('data-health','neutral')
    await second.locator('[id^="sm-token"]').fill('second-supply-token')
    await second.locator('.sm-toggle').click()
    await expect(second.locator('.sm-state')).to_have_text('已停用')
    await expect(second).to_have_attribute('data-health','neutral')
    await second.locator('.sm-toggle').click()
    await expect(second.locator('.sm-state')).to_have_text('已配置')
    await second.locator('.sm-test').click()
    await expect(second).to_have_attribute('data-health','ok')
    await page.reload()
    await expect(second.locator('[id^="sm-token"]')).to_have_value('second-supply-token')
    await expect(default.locator('#sm-token')).to_have_value('original-supply-token')
    await expect(second).to_have_attribute('data-health','ok')
    await root.locator('.sm-add').click()
    draft = root.locator('[data-token-id^="draft-"]')
    await draft.locator('[id^="sm-token"]').fill('original-supply-token')
    await draft.locator('.sm-save').click()
    await expect(draft.locator('.sm-result')).to_contain_text('该 Token 已存在')
    await expect(draft.locator('[id^="sm-token"]')).to_have_value('original-supply-token')
    await draft.locator('.sm-remove').click()
    assert await root.locator('.sm-token-card').count() == 2
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    for card in (default,second):
        assert await card.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
        assert await card.locator('p').count() == 0
    name = ('mobile' if mobile else 'desktop') + ('-okad' if prefix else '')
    await root.scroll_into_view_if_needed()
    await page.screenshot(path=str(OUTPUT / (name+'.png')))
    await second.locator('.sm-remove').click()
    await expect(second).to_have_count(0)
    assert rows[0]['token'] == 'original-supply-token'
    if mobile: await page.locator('#okad-mobile-menu').click()
    await page.locator('#extm-nav').click()
    await expect(root).not_to_be_visible()
    await expect(page.locator('#extm-mail-state')).to_have_text('已配置')
    assert not errors, errors
    assert not escaped, escaped
    await context.close()
    print('PASS',prefix or '/',name,': independent edits/checks, original Token, watermarks, polling and navigation',flush=True)


async def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            for prefix in ('','/okad'):
                for mobile in (False,True): await scenario(browser,prefix,mobile)
        finally: await browser.close()

if __name__ == '__main__': asyncio.run(main())
