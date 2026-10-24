"""Complete historical mailbox credentials and copy scopes, using synthetic data only."""
import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from email_import_batches_ui import EmailFixtures, choose
from mobile_workspace_ui import fits, dialog_fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'email-formats-preview'


class FormatFixtures(EmailFixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        base = self.mail[0]
        self.mail = [
            dict(base, id=9001, email='history@example.test', password='Synthetic<&Password',
                 client_id='11111111-2222-3333-4444-555555555555',
                 refresh_token='M.'+'SyntheticToken'*600),
            dict(base, id=9000, email='link@example.test', is_used=False, import_batch=None,
                 password='SyntheticPass', mail_url='moemail://edu6.site?api_key=mk_synthetic&email_id=17'),
            *[dict(base, id=i, email=f'old{i}@example.test', import_batch='20261025') for i in range(205, 0, -1)]
        ]
        self.formats_requests, self.fail_formats, self.hold_next = [], False, None

    def matching(self, data):
        rows = self.mail
        if data.get('ids') is not None:
            rows = [r for r in rows if r['id'] in data['ids']]
        if data.get('keyword'):
            rows = [r for r in rows if data['keyword'] in r['email']]
        if data.get('is_used') is not None:
            rows = [r for r in rows if r['is_used'] == data['is_used']]
        if data.get('import_batch'):
            rows = [r for r in rows if r['import_batch'] == data['import_batch']]
        return rows

    def content(self, data):
        rows = self.matching(data)
        keys, separator = (('email','password','refresh_token','client_id'), '|') if data.get('format') == 'pipe' else (
            ('email','password','client_id','refresh_token'), '----')
        return '\n'.join(separator.join([r.get(k) or '' for k in keys]+([r['mail_url']] if r.get('mail_url') else [])) for r in rows)

    async def serve(self, route):
        url = urlparse(route.request.url)
        path = url.path.removeprefix(self.prefix)
        if path == '/api/emails/formats':
            data = route.request.post_data_json
            self.formats_requests.append(data)
            gate, self.hold_next = self.hold_next, None
            if gate:
                await gate.wait()
            if self.fail_formats:
                return await route.fulfill(status=503, json={'detail': '模拟读取失败'})
            return await route.fulfill(json=dict(total=len(self.matching(data)), content=self.content(data)))
        if path == '/api/emails' and route.request.method == 'GET':
            query = {k:v[0] for k,v in parse_qs(url.query).items()}
            if 'is_used' in query:
                query['is_used'] = query['is_used'] == 'true'
            rows = self.matching(query)
            size, page = int(query.get('size', 200)), int(query.get('page', 1))
            return await route.fulfill(json=dict(items=rows[(page-1)*size:page*size], total=len(rows)))
        return await super().serve(route)


async def check(browser, prefix, width):
    context = await browser.new_context(viewport=dict(width=width, height=1000 if width > 800 else 844))
    fixture, errors = FormatFixtures(prefix), []
    await context.route('**/*', fixture.serve)
    await context.add_init_script('''
      localStorage.setItem('okad_token','synthetic-formats');
      window.copiedFormats=[];
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{
        if(window.failCopy)throw new Error('synthetic denial'); window.copiedFormats.push(text);
      }}});
      document.execCommand=command=>{
        if(window.failFallback)return false;
        const input=document.activeElement;
        window.copiedFormats.push(input.value.slice(input.selectionStart,input.selectionEnd));return true;
      };
    ''')
    page = await context.new_page()
    page.set_default_timeout(10000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto('http://format.test'+prefix+'/email')
    ws = page.locator('#email-workspace')
    await expect(ws).to_contain_text('history@example.test')
    assert await ws.locator('tbody > tr').count() == 200
    await ws.get_by_role('button', name='历史邮箱格式', exact=True).click()
    drawer = page.locator('.ws-email-formats')
    output = drawer.get_by_role('textbox', name='完整邮箱格式')
    await expect(drawer.get_by_role('status')).to_contain_text('共 207 条')
    expected = fixture.content({'format':'standard'})
    await expect(output).to_have_value(expected)
    assert len((await output.input_value()).splitlines()) == 207
    await drawer.get_by_role('button', name='复制全部', exact=True).click()
    assert await page.evaluate('window.copiedFormats.at(-1)') == expected
    await drawer.get_by_role('button', name='选择全部', exact=True).click()
    assert await output.evaluate('el=>el.selectionEnd-el.selectionStart') == len(expected)
    await choose(page, drawer.locator('.ws-field').nth(1), '竖线分隔（RefreshToken 在前）')
    expected = fixture.content({'format':'pipe'})
    await expect(output).to_have_value(expected)
    await page.evaluate('window.failCopy=true')
    await drawer.get_by_role('button', name='复制全部', exact=True).click()
    assert await page.evaluate('window.copiedFormats.at(-1)') == expected
    await page.evaluate('window.failFallback=true')
    await drawer.get_by_role('button', name='复制全部', exact=True).click()
    await expect(page.locator('.n-message').last).to_contain_text('复制失败')
    await page.evaluate('window.failCopy=false;window.failFallback=false')
    await dialog_fits(page, '.ws-email-formats')
    if not prefix:
        await page.screenshot(path=str(OUTPUT/f'formats-{width}.png'), animations='disabled')
    await drawer.get_by_role('button', name='关闭', exact=True).click()

    if width <= 800:
        await ws.get_by_role('button', name='筛选条件').click()
    await ws.locator('.ws-filter-body input').first.fill('history')
    await ws.get_by_role('button', name='搜索', exact=True).click()
    await expect(ws.locator('tbody > tr')).to_have_count(1)
    await choose(page, ws.locator('.ws-field').filter(has=page.get_by_text('导入批次', exact=True)), '20261024')
    await choose(page, ws.locator('.ws-field').filter(has=page.get_by_text('使用状态', exact=True)), '已使用')
    await ws.get_by_role('button', name='历史邮箱格式', exact=True).click()
    await expect(drawer.get_by_role('status')).to_contain_text('共 1 条')
    request = fixture.formats_requests[-1]
    assert request == dict(keyword='history', import_batch='20261024', is_used=True, format='pipe')
    await expect(output).to_have_value(fixture.content(request))
    await drawer.get_by_role('button', name='关闭', exact=True).click()
    await ws.get_by_role('button', name='重置', exact=True).click()
    await expect(ws.locator('tbody > tr')).to_have_count(200)
    await ws.locator('tbody > tr').nth(0).get_by_role('checkbox').click()
    await ws.locator('tbody > tr').nth(1).get_by_role('checkbox').click()
    await ws.get_by_role('button', name='历史邮箱格式', exact=True).click()
    await expect(drawer.get_by_role('status')).to_contain_text('共 2 条')
    assert fixture.formats_requests[-1] == dict(ids=[9001,9000], format='pipe')
    await expect(output).to_have_value(fixture.content(fixture.formats_requests[-1]))
    await drawer.get_by_role('button', name='关闭', exact=True).click()

    await ws.get_by_role('button', name='邮箱格式', exact=True).first.click()
    await expect(drawer.get_by_role('status')).to_contain_text('共 1 条')
    assert fixture.formats_requests[-1] == dict(ids=[9001], format='pipe')
    await expect(output).to_have_value(fixture.content(fixture.formats_requests[-1]))
    if width <= 800:
        await page.set_viewport_size(dict(width=320,height=360))
        await dialog_fits(page, '.ws-email-formats')
        box = await drawer.get_by_role('button', name='复制全部', exact=True).bounding_box()
        assert box['y'] >= 0 and box['y']+box['height'] <= 361, box
        await page.set_viewport_size(dict(width=width,height=844))
    await drawer.get_by_role('button', name='关闭', exact=True).click()

    fixture.fail_formats = True
    await ws.get_by_role('button', name='历史邮箱格式', exact=True).click()
    await expect(drawer.get_by_role('alert')).to_contain_text('模拟读取失败')
    await expect(output).to_have_value('')
    await expect(drawer.get_by_role('button', name='复制全部', exact=True)).to_be_disabled()
    fixture.fail_formats = False
    await drawer.get_by_role('button', name='重试', exact=True).click()
    await expect(drawer.get_by_role('status')).to_contain_text('共 2 条')
    fixture.hold_next = gate = asyncio.Event()
    await choose(page, drawer.locator('.ws-field').nth(1), '四横线分隔（ClientID 在前）')
    await expect(output).to_have_attribute('aria-busy', 'true')
    await expect(drawer.get_by_role('button', name='复制全部', exact=True)).to_be_disabled()
    await choose(page, drawer.locator('.ws-field').nth(1), '竖线分隔（RefreshToken 在前）')
    await expect(output).to_have_value(fixture.content({'ids':[9001,9000],'format':'pipe'}))
    async with page.expect_response(lambda response: response.url.endswith('/api/emails/formats') and response.request.post_data_json.get('format') == 'standard'):
        gate.set()
    await expect(output).to_have_value(fixture.content({'ids':[9001,9000],'format':'pipe'}))
    await page.keyboard.press('Escape')
    await expect(drawer).not_to_be_visible()
    await expect(page.locator('#email-format-content')).to_have_count(0)

    await page.evaluate("localStorage.setItem('okad-theme','dark')")
    await page.reload()
    await ws.get_by_role('button', name='历史邮箱格式', exact=True).click()
    await expect(drawer.get_by_role('status')).to_contain_text('共 207 条')
    assert await drawer.evaluate('el=>getComputedStyle(el).backgroundColor') != 'rgb(255, 255, 255)'
    await dialog_fits(page, '.ws-email-formats')
    await fits(page, '#email-workspace')
    if not prefix:
        await page.screenshot(path=str(OUTPUT/f'dark-{width}.png'), animations='disabled')
    assert not fixture.writes, fixture.writes
    assert not fixture.escaped, fixture.escaped
    assert not errors, errors
    await context.close()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('MAIL_BROWSER','chromium')).launch()
        for prefix in ('','/okad'):
            for width in (1440,390):
                await check(browser,prefix,width)
                print(f'PASS full email formats {prefix or "/"} {width}px',flush=True)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
