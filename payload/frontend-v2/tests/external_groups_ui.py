"""Group creation, import draft and assignment with real Vue controls and isolated APIs."""
import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from external_controls import select_value
from mobile_workspace_ui import Fixtures, fits, dialog_fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'external-groups-preview'


class GroupFixtures(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.groups = [{'id': 1, 'name': '客户 A', 'count': 3}]
        self.calls = []
        for i, row in enumerate(self.rows):
            row.update(group_id=1 if i < 3 else None, group_name='客户 A' if i < 3 else '',
                       otp_mode='vietnam' if i == 0 else 'manual', uses_supply_mail=False)

    async def serve(self, route):
        url = urlparse(route.request.url)
        if url.netloc != 'groups.test':
            self.escaped.append(route.request.url)
            return await route.abort()
        path, method = url.path.removeprefix(self.prefix), route.request.method
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        if path == '/api/external/groups':
            if method == 'GET':
                return await route.fulfill(json=self.groups)
            payload = route.request.post_data_json
            self.writes.append((path, payload))
            if any(g['name'] == payload['name'] for g in self.groups):
                return await route.fulfill(status=409, json={'detail': '分组名称已存在'})
            group = dict(id=len(self.groups)+1, name=payload['name'], count=0)
            self.groups.append(group)
            return await route.fulfill(status=201, json=group)
        if path == '/api/external/members':
            self.calls.append(query)
            rows = self.rows
            if query.get('group_id'):
                rows = [r for r in rows if (r['group_id'] or 0) == int(query['group_id'])]
            if query.get('account_type') == 'vietnam':
                rows = [r for r in rows if r['otp_mode'] == 'vietnam']
            page, size = int(query['page']), int(query['size'])
            return await route.fulfill(json={'items': rows[(page-1)*size:page*size], 'total': len(rows)})
        if path in ('/api/external/members/import', '/api/external/members/group'):
            payload = route.request.post_data_json
            self.writes.append((path, payload))
            if path.endswith('/group'):
                for row in self.rows:
                    if row['id'] in payload['ids']:
                        row.update(group_id=payload['group_id'], group_name=next((g['name'] for g in self.groups if g['id'] == payload['group_id']), ''))
                return await route.fulfill(json={'updated': len(payload['ids']), 'message': '分组已保存'})
            return await route.fulfill(json=dict(created=1, updated=0, skipped=0, failed=0))
        return await super().serve(route)


async def choose(page, selector, label):
    await page.locator(selector).locator('.n-base-selection').click()
    option = page.locator('.n-base-select-option:visible').filter(has=page.get_by_text(label, exact=True))
    await expect(option).to_have_count(1)
    await option.click()


async def check(browser, prefix, width):
    context = await browser.new_context(viewport={'width': width, 'height': 950}, locale='zh-CN')
    fixtures, errors = GroupFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-group-ui')")
    page = await context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto('http://groups.test' + prefix + '/external-members')
    await expect(page.locator('[data-member="1"] .extm-group-tag')).to_have_text('客户 A')
    await choose(page, '#extm-f-group', '客户 A')
    await expect(page.locator('#extm-total')).to_have_text('3')
    await choose(page, '#extm-f-company', '越南账号')
    await expect(page.locator('#extm-total')).to_have_text('1')
    assert fixtures.calls[-1]['account_type'] == 'vietnam' and fixtures.calls[-1]['group_id'] == '1'
    await page.locator('#extm-open-import').click()
    await page.locator('#extm-group-name').fill('客户 A')
    await page.locator('#extm-create-group').click()
    await expect(page.locator('#extm-import-drawer')).to_contain_text('分组名称已存在')
    await page.locator('#extm-group-name').fill('新分组 <客户 B>')
    await page.locator('#extm-create-group').click()
    await expect(page.locator('#extm-import-group')).to_contain_text('新分组 <客户 B>')
    await page.locator('#extm-import').fill('new@example.com')
    await page.locator('#extm-import-done').click()
    await page.locator('#extm-open-import').click()
    await expect(page.locator('#extm-import')).to_have_value('new@example.com')
    await expect(page.locator('#extm-import-group')).to_contain_text('新分组 <客户 B>')
    await dialog_fits(page, '#extm-import-drawer')
    await page.screenshot(path=str(OUTPUT / f'import-{prefix.strip("/") or "root"}-{width}.png'))
    await page.locator('#extm-do-import').click()
    await expect(page.locator('#extm-import-result')).to_contain_text('导入完成')
    assert fixtures.writes[-1][1] == dict(content='new@example.com', on_duplicate='skip', group_id=2)
    await page.locator('#extm-import-done').click()
    await page.locator('[data-member="1"] .extm-rowck').check()
    await page.locator('#extm-batch-group').scroll_into_view_if_needed()
    await choose(page, '#extm-batch-group', '新分组 <客户 B>')
    await expect(page.locator('#extm-total')).to_have_text('0')
    assert fixtures.writes[-1] == ('/api/external/members/group', {'ids': [1], 'group_id': 2})
    await page.locator('#extm-reset-filters').click()
    await choose(page, '#extm-f-group', '新分组 <客户 B>')
    await expect(page.locator('#extm-total')).to_have_text('1')
    await expect(page.locator('[data-member="1"] .extm-group-tag')).to_have_text('新分组 <客户 B>')
    await page.screenshot(path=str(OUTPUT / f'filtered-{prefix.strip("/") or "root"}-{width}.png'))
    await fits(page, '#extm-embed')
    assert not errors, errors
    assert not fixtures.escaped, fixtures.escaped
    await context.close()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('GROUP_BROWSER', 'chromium')).launch()
        for prefix in ('', '/okad'):
            for width in (1440, 390):
                await check(browser, prefix, width)
        await browser.close()
    print('PASS: groups create/duplicate/import/draft/filter/assign on desktop and mobile, root and /okad')


if __name__ == '__main__':
    asyncio.run(main())
