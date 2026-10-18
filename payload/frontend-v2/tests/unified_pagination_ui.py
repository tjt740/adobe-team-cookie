"""Exercise common page sizes on every list with local assets and mocked APIs."""
import asyncio
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures
from jobs_workspace_ui import job

COUNT = 1207


class PaginationFixtures(Fixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.calls = []
        self.rows = [dict(self.member, id=i, email=f'account{i:04d}@example.test', otp_mode='auto') for i in range(1, COUNT + 1)]
        self.tasks = [job(i, 'pool_login', email=f'account{i:04d}@example.test') for i in range(COUNT, 0, -1)]

    async def serve(self, route):
        url = urlparse(route.request.url)
        path = url.path.removeprefix(self.prefix) if self.prefix else url.path
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        self.calls.append((path, query))
        page, size = int(query.get('page', 1)), int(query.get('size', 200))
        data = None
        if path in ('/api/adobe-accounts', '/api/emails', '/api/pool', '/api/external/members') or path.endswith('/members') and path.startswith('/api/adobe-accounts/'):
            rows = [dict(row, admin_id=1, is_valid=True, has_org=True, member_count=COUNT,
                         status='registered', credits=4000, registered=True, is_imported=True, has_token=True)
                    for row in self.rows]
            data = dict(items=rows[(page - 1) * size:page * size], total=COUNT, page=page, size=size)
        elif path == '/api/sub2/accounts':
            data = dict(ok=True, items=[dict(row, name=row['email'], platform='adobe', status='active', groups=[])
                                          for row in self.rows[(page - 1) * size:page * size]], total=COUNT)
        elif path == '/api/admin/users':
            data = [dict(id=i, username=f'user{i}', is_active=True, is_superuser=True) for i in range(COUNT)]
        elif path == '/api/logs':
            data = dict(items=[dict(id=i, time='2026-10-13 12:00:00', level='INFO', source='test', message=f'Log {i}') for i in range(COUNT)], total=COUNT)
        elif path == '/api/adobe-accounts/jobs' or path.startswith('/api/external/members/') and path.endswith('/jobs'):
            data = self.tasks[:int(query.get('limit', 200))]
        elif path.startswith('/api/adobe-accounts/jobs/'):
            data = dict(self.tasks[0])
            data['extra'] = {'items': [dict(id=i, email=f'account{i}@example.test', status='done', message='完成') for i in range(COUNT)]}
            data['trace']['accounts'] = []
            data['logs'] = [f'12:00:00 日志 {i}' for i in range(COUNT)]
            data['log_total'] = COUNT
        elif path == '/api/integration/sources':
            data = dict(items=[dict(source_key=f'external:{row["id"]}', email=row['email'], source='外部子号', has_cookie=True, auto_recovery=True, version=1)
                               for row in self.rows[(page - 1) * size:page * size]], total=COUNT, page=page)
        elif path == '/api/integration/status':
            start = (int(query.get('jobs_page', 1)) - 1) * int(query.get('jobs_size', 200))
            end = start + int(query.get('jobs_size', 200))
            data = dict(config=dict(base_url='http://sub2.test', enabled=True, key_configured=True, site_id='fixture'),
                        counts={}, active_jobs=0, checked_at=1, jobs_total=COUNT,
                        jobs=[dict(job_id=f'job{i}', source_key=f'external:{i}', state='done', email=f'job{i}@example.test', created_at=1)
                              for i in range(start, min(end, COUNT))])
        if data is None:
            return await super().serve(route)
        await route.fulfill(json=data)


async def exercise(page, scope, row_selector):
    await expect(scope.locator('.okad-page-size, .extv-page-size').first).to_be_visible()
    if await scope.locator('.extv-page-size').count():
        from external_controls import select_value, expect_select
        form = scope.locator('.extv-page-size')
        custom = form.locator('input[name=pageSize]')
        await select_value(page, '#extm-page-size', '1000')
        await expect(scope.locator(row_selector)).to_have_count(1000, timeout=20000)
        await custom.fill('137')
        await form.locator('button[type=submit]').click()
        await expect(scope.locator(row_selector)).to_have_count(137, timeout=15000)
        await expect_select(page, '#extm-page-size', '137')
        for invalid in ['0', '-1', '1.5', '10001']:
            await custom.fill(invalid)
            await form.locator('button[type=submit]').click()
            assert not await custom.evaluate('(el) => el.checkValidity()')
            await expect_select(page, '#extm-page-size', '137')
        await custom.fill('137')
        return
    form = scope.locator('.okad-page-size').first
    select, custom = form.locator('select'), form.locator('input[name=pageSize]')
    await expect(select).to_be_enabled()
    values = await select.locator('option').evaluate_all('(nodes) => nodes.map(n => n.value)')
    assert set(['100', '200', '300', '400', '500', '1000']).issubset(values), values
    await select.select_option('1000')
    await expect(scope.locator(row_selector)).to_have_count(1000, timeout=20000)
    await expect(custom).to_be_enabled()
    await custom.fill('137')
    await form.locator('button[type=submit]').click()
    await expect(scope.locator(row_selector)).to_have_count(137, timeout=15000)
    await expect(select).to_have_value('137')
    for invalid in ['0', '-1', '1.5', '10001']:
        await custom.fill(invalid)
        await form.locator('button[type=submit]').click()
        assert not await custom.evaluate('(el) => el.checkValidity()')
        await expect(select).to_have_value('137')
    await custom.fill('137')


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for prefix in ('', '/okad'):
            context = await browser.new_context(viewport={'width': 1600, 'height': 1000})
            fixtures, errors = PaginationFixtures(prefix), []
            await context.route('**/*', fixtures.serve)
            await context.add_init_script("localStorage.setItem('okad_token','synthetic-pagination')")
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            for route, selector, rows in [
                ('external-members', '#extm-embed', 'tr[data-member]'),
                ('adobe', '#adobe-workspace', '.n-data-table-tbody tr'),
                ('pool', '#pool-workspace', '.n-data-table-tbody tr'),
                ('email', '#email-workspace', '.n-data-table-tbody tr'),
                ('logs', '#logs-workspace', '.n-data-table-tbody tr'),
                ('jobs', '#jobs-workspace', '.task-card'),
                ('sub2', '#sub2-panel', '#s2-tbody tr'),
                ('settings', '#okad-user-management', 'tbody tr'),
                ('integration', '#integration-panel', '#integration-sources tr')]:
                await page.goto('http://pagination.test' + prefix + '/' + route)
                scope = page.locator(selector)
                await expect(scope).to_be_visible()
                await exercise(page, scope, rows)
                print('PASS', prefix or '/', route, flush=True)
                if route == 'adobe':
                    await scope.locator('.n-data-table-tbody tr').first.get_by_role('button', name='成员', exact=True).click()
                    await exercise(page, page.locator('.n-drawer'), '.n-data-table-tbody tr')
                if route == 'external-members':
                    await scope.locator('tr[data-member]').first.locator('.extm-toggle').click()
                    await exercise(page, page.locator('.extm-detail').first, '.extm-history tbody tr')
                if route == 'integration':
                    await exercise(page, scope.locator('.integration-section').last, '.integration-job')
            await page.goto('http://pagination.test' + prefix + '/jobs?id=1')
            await exercise(page, page.locator('.task-account-results'), '.task-account-row')
            await page.get_by_role('tab', name='执行记录').click()
            await exercise(page, page.locator('#jobs-workspace'), '.task-timeline li')
            assert not errors, errors
            assert not fixtures.writes, fixtures.writes
            await context.close()
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
