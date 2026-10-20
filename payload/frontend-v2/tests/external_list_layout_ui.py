"""Compact external list: real browser layout and preserved account actions.

Only local frontend files and synthetic API responses are used.
"""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures, fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'external-list-preview'


class ListFixtures(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.codes = [401, 408]
        self.available = True
        self.rows = [dict(self.member, id=i, email=f'{name}@example.test',
                          note='', has_adobe_password=i == 1, otp_mode='auto',
                          uses_supply_mail=i > 2, subscription_ok=i > 2,
                          credits_available=10 if i < 3 else 3200 + i * 61,
                          credits_total=10 if i < 3 else 4000,
                          last_login_at='2026-10-20T13:32:00Z',
                          sub2_status='synced', sub2_synced_at='2026-10-20T13:33:12Z',
                          account_profile=dict(current_kind='personal' if i < 3 else 'organization',
                                               fallback_reason='组织邀请激活失败（HTTP 403）' if i < 3 else '',
                                               profiles=[], profiles_complete=True),
                          latest_job=dict(id=100+i, status='done',
                                          extra={'items': [{'id': i, 'status': 'done'}]}))
                     for i, name in enumerate(['le.teppo76', 'kenneth.wheeler', 'cicni26727',
                                               'crnfv428284', 'yenco.feilen', 'gisselle.polliche',
                                               'pxgsw8631', 'isesa70337', 'xxcto94229',
                                               'tvoou446055', 'design.team', 'studio.account'], 1)]

    async def serve(self, route):
        path = urlparse(route.request.url).path.removeprefix(self.prefix)
        if path == '/api/external/groups':
            return await route.fulfill(json=[])
        if path == '/api/external/members/sub2-stock':
            return await route.fulfill(json=dict(ok=self.available, configured=True,
                checked_at='2026-10-20T13:35:00Z', items={r['id']: dict(
                    email=r['email'], in_stock=True, account_ids=[r['id']],
                    account_health=dict(state='error', codes=self.codes,
                                        errors=[dict(code=c) for c in self.codes])) for r in self.rows}))
        if path == '/api/external/members/1/mail/messages':
            return await route.fulfill(json=dict(items=[]))
        if path == '/api/external/members/batch-delete':
            self.writes.append((path, route.request.post_data_json))
            ids = route.request.post_data_json['ids']
            self.rows = [r for r in self.rows if r['id'] not in ids]
            return await route.fulfill(json={'message': '已删除'})
        return await super().serve(route)


async def scenario(browser, prefix):
    context = await browser.new_context(viewport={'width':1600, 'height':1100},
                                        locale='zh-CN', timezone_id='Asia/Shanghai')
    fixtures, errors = ListFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-list-layout')")
    page = await context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto('http://list.test' + prefix + '/external-members')
    await expect(page.locator('tr[data-member]')).to_have_count(12)
    row = page.locator('[data-member="1"]')
    await expect(row.locator('[data-sub2-health]')).to_have_text('Sub2 401 / 408')
    await expect(row.locator('[data-sub2-health]')).to_have_count(1)
    await expect(row.locator('.extm-status')).to_contain_text('本轮成功')
    await expect(row.locator('.extm-credentials')).to_have_text('有 Cookie · 有密码')
    await expect(page.locator('#extm-batch-profile')).not_to_be_visible()
    await row.locator('.extm-rowck').check()
    await expect(page.locator('#extm-batch-profile')).to_be_visible()
    await expect(page.locator('#extm-batch-login')).to_be_enabled()
    await page.locator('#extm-more-actions>summary').click()
    await expect(page.locator('#extm-more-actions>div')).to_be_visible()
    await page.keyboard.press('Escape')
    await row.locator('.extm-rowck').uncheck()

    for width in (1600, 1440):
        await page.set_viewport_size({'width':width, 'height':1100})
        await page.locator('.extm-t').evaluate('''el => new Promise(resolve =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)))''')
        assert await page.locator('.extm-tw').evaluate('el=>el.scrollWidth<=el.clientWidth+1'), width
        await fits(page, '#extm-embed')
    if not prefix:
        await page.set_viewport_size({'width':1600, 'height':1100})
        await page.locator('.extm-batch-row').evaluate('el=>el.scrollLeft=0')
        await page.mouse.move(0, 0)
        await page.screenshot(path=str(OUTPUT/'desktop.png'), animations='disabled')
        await page.locator('.extm-tw').screenshot(path=str(OUTPUT/'account-list.png'), animations='disabled')

    # Menu stays on screen even when the final row touches the viewport edge.
    trigger = row.locator('[data-row-more]')
    await trigger.click()
    menu = page.locator('#extm-row-menu')
    await expect(menu).to_be_visible()
    await expect(trigger).to_have_attribute('aria-expanded', 'true')
    await menu.locator('[data-note]').click()
    dialog = page.locator('#extm-note-dialog')
    await expect(dialog).to_be_visible()
    await dialog.locator('textarea').fill('简化列表后的备注')
    await dialog.locator('[type=submit]').click()
    await expect(dialog).to_have_count(0)
    await expect(trigger).to_be_focused()
    await trigger.click()
    await page.keyboard.press('Escape')
    await expect(menu).not_to_be_visible()
    await expect(trigger).to_have_attribute('aria-expanded', 'false')
    await trigger.click()
    await trigger.click()
    await expect(menu).not_to_be_visible()
    await trigger.click()
    await menu.locator('[data-mail]').click()
    await expect(page.locator('#extm-mail-dialog')).to_be_visible()
    await page.keyboard.press('Escape')

    await row.locator('.extm-toggle').click()
    await expect(page.locator('.extm-account-times')).to_contain_text('2026-10-12 08:00')
    await expect(page.locator('.extm-account-times [data-sub2-pushed-at]')).to_have_text('2026-10-20 21:33:12')
    await row.locator('.extm-toggle').click()
    fixtures.available = False
    await page.locator('#extm-refresh').click()
    await expect(row.locator('[data-sub2-health]')).to_have_text('Sub2 状态暂不可用')
    fixtures.available = True
    fixtures.codes = [401, 408, 429, 503]
    await page.locator('#extm-refresh').click()
    await expect(row.locator('[data-sub2-health]')).to_have_text('Sub2 401 / 408 / 429 / 503')

    for width in (390, 320):
        await page.set_viewport_size({'width':width,'height':950})
        await fits(page, '#extm-embed')
        assert await page.evaluate('''() => document.querySelector('.extm-pagination').getBoundingClientRect().top >=
            document.querySelector('.extm-tw').getBoundingClientRect().bottom - 1'''), 'Pager overlaps account cards'
        await row.scroll_into_view_if_needed()
        await trigger.click()
        await expect(menu).to_be_visible()
        box = await menu.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= width, box
        assert await menu.locator('button').first.evaluate('el=>el.getBoundingClientRect().height') >= 44
        await page.keyboard.press('Escape')
        if not prefix and width == 390:
            await page.mouse.move(0, 0)
            await page.screenshot(path=str(OUTPUT/'mobile.png'), animations='disabled')

    await page.evaluate("localStorage.setItem('okad-theme','dark')")
    await page.set_viewport_size({'width':1600,'height':1100})
    await page.reload()
    await expect(page.locator('tr[data-member]')).to_have_count(12)
    if not prefix:
        await page.screenshot(path=str(OUTPUT/'dark.png'), animations='disabled')
    await page.locator('[data-member="12"] [data-row-more]').click()
    await page.locator('#extm-row-menu [data-del]').click()
    await expect(page.locator('tr[data-member]')).to_have_count(11)
    assert fixtures.writes == [('/api/external/members/1/note', {'note': '简化列表后的备注'}),
                               ('/api/external/members/batch-delete', {'ids': [12]})], fixtures.writes
    assert not errors and not fixtures.escaped, (errors, fixtures.escaped)
    await context.close()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('LIST_BROWSER','chromium')).launch()
        for prefix in ('', '/okad'):
            await scenario(browser, prefix)
        await browser.close()
    print('PASS: compact list, combined health codes, selection, notes/mail/delete, time details, '
          'unavailable state, mobile menu bounds and dark theme, root and /okad')


if __name__ == '__main__':
    asyncio.run(main())
