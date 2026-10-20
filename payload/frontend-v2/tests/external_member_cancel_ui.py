"""Single-account cancellation with local assets and synthetic APIs only."""
import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect
from external_list_layout_ui import ListFixtures
from mobile_workspace_ui import fits

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'member-stop-preview'


class CancelFixtures(ListFixtures):
    def __init__(self, prefix):
        super().__init__(prefix)
        self.rows = self.rows[:6]
        self.rows[1]['otp_challenge'] = dict(request_id='a' * 32,
            email=self.rows[1]['email'], expires_at=1999999999)
        self.job = dict(id=90, type='external_login', status='running', target=5,
            success=1, fail=1, cancelled_count=1, created_at=1792500000,
            logs=[], log_total=0, extra={'items': [dict(id=i, status=phase)
                for i, phase in [(1,'pending'), (2,'running'), (3,'done'),
                                 (5,'failed'), (6,'cancelled')]]})
        self.paused = dict(self.job, id=91, status='paused', target=1,
            success=0, fail=0, cancelled_count=0,
            extra={'items': [dict(id=4, status='pending')]})
        self.gate, self.entered = asyncio.Event(), asyncio.Event()
        self.fail_next = True
        self.sync()

    def sync(self):
        for row in self.rows:
            job = self.paused if row['id'] == 4 else self.job
            item = next(i for i in job['extra']['items'] if i['id'] == row['id'])
            row['latest_job'] = dict(job, item_status=item['status'])

    def finish(self, mid):
        job = self.paused if mid == 4 else self.job
        next(i for i in job['extra']['items'] if i['id'] == mid)['status'] = 'cancelled'
        job['cancelled_count'] += 1
        if mid == 4:
            job['status'] = 'cancelled'
        self.sync()

    async def serve(self, route):
        req = route.request
        path = urlparse(req.url).path.removeprefix(self.prefix)
        if req.method == 'POST' and path.endswith('/cancel-job'):
            self.writes.append((path, req.post_data_json))
            mid = int(path.split('/')[-2])
            assert req.post_data_json == {'job_id': 91 if mid == 4 else 90}
            if mid == 4 and self.fail_next:
                self.fail_next = False
                return await route.fulfill(status=503, json={'detail':'模拟终止失败，请重试'})
            if mid == 2:
                self.entered.set()
                await self.gate.wait()
                next(i for i in self.job['extra']['items'] if i['id'] == mid)['status'] = 'cancelling'
                self.sync()
            else:
                self.finish(mid)
            return await route.fulfill(json={'message':'已请求终止本账号，同批其他账号继续执行'})
        if re.fullmatch(r'/api/external/members/\d+/jobs', path):
            return await route.fulfill(json=[self.paused if '/4/' in path else self.job])
        if path in ('/api/adobe-accounts/jobs/90', '/api/adobe-accounts/jobs/91'):
            return await route.fulfill(json=self.paused if path.endswith('/91') else self.job)
        return await super().serve(route)


async def scenario(browser, prefix):
    context = await browser.new_context(viewport={'width':1600,'height':1100},
        locale='zh-CN', timezone_id='Asia/Shanghai')
    fixtures, errors = CancelFixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-row-stop')")
    page = await context.new_page()
    page.set_default_timeout(8000)
    page.on('pageerror', lambda e: errors.append(str(e)))
    await page.goto('http://row-stop.test' + prefix + '/external-members')
    await expect(page.locator('tr[data-member]')).to_have_count(6)
    for mid in (1,2,4):
        await expect(page.locator(f'[data-stop-member="{mid}"]')).to_be_enabled()
    for mid in (3,5,6):
        await expect(page.locator(f'[data-stop-member="{mid}"]')).to_have_count(0)
    await expect(page.locator('[data-login="6"]')).to_be_enabled()
    await expect(page.locator('[data-otp="2"]')).to_be_enabled()
    await expect(page.locator('[data-member="4"] .extm-status')).to_contain_text('已暂停')

    for width in (1600,1440,390,320):
        await page.set_viewport_size({'width':width,'height':1100})
        await fits(page, '#extm-embed')
        if width >= 1440:
            assert await page.locator('.extm-tw').evaluate('el=>el.scrollWidth<=el.clientWidth+1'), width
        for mid in (1,2,4):
            row = page.locator(f'[data-member="{mid}"]')
            assert await row.locator('.extm-actions').evaluate('el=>el.scrollWidth<=el.clientWidth+1'), (width,mid)
            await row.locator('[data-stop-member]').click(trial=True)
            if width <= 390:
                assert await row.locator('[data-stop-member]').evaluate('el=>el.getBoundingClientRect().height') >= 44
        if not prefix and width in (1600,390):
            await page.evaluate('scrollTo(0,0)')
            await page.screenshot(path=str(OUTPUT/f'{"desktop" if width==1600 else "mobile"}.png'), animations='disabled')

    await page.set_viewport_size({'width':1600,'height':1100})
    await page.evaluate("localStorage.setItem('okad-theme','dark')")
    await page.reload()
    await expect(page.locator('[data-stop-member="2"]')).to_be_enabled()
    if not prefix:
        await page.screenshot(path=str(OUTPUT/'dark.png'), animations='disabled')
    await page.evaluate("localStorage.setItem('okad-theme','light')")
    await page.reload()

    # A queued stop takes effect immediately without changing its active sibling.
    await page.locator('[data-stop-member="1"]').click()
    await expect(page.locator('[data-member="1"] .extm-status')).to_contain_text('已终止')
    await expect(page.locator('[data-login="1"]')).to_be_enabled()
    await expect(page.locator('[data-stop-member="2"]')).to_be_enabled()
    await expect(page.locator('[data-member="3"] .extm-status')).to_contain_text('本轮成功')

    # A pending response and subsequent worker shutdown both block duplicate requests.
    await page.locator('[data-stop-member="2"]').click()
    await asyncio.wait_for(fixtures.entered.wait(), 3)
    await expect(page.locator('[data-stop-member="2"]')).to_be_disabled()
    await expect(page.locator('[data-stop-member="2"]')).to_have_text('终止中')
    await expect(page.locator('[data-otp="2"]')).to_have_count(0)
    await page.locator('[data-stop-member="2"]').evaluate('el=>el.click()')
    fixtures.gate.set()
    await expect(page.locator('[data-member="2"] .extm-status')).to_contain_text('终止中')
    await expect(page.locator('[data-stop-member="2"]')).to_be_disabled()
    assert len([w for w in fixtures.writes if '/2/' in w[0]]) == 1
    fixtures.finish(2)  # Simulate a worker leaving its next cancellation checkpoint.
    await page.locator('#extm-refresh').click()
    await expect(page.locator('[data-member="2"] .extm-status')).to_contain_text('已终止')
    await expect(page.locator('[data-login="2"]')).to_be_enabled()
    await expect(page.locator('[data-otp="2"]')).to_have_count(0)  # Even a stale OTP is retired.

    # Failed requests remain retryable; paused queues support the same direct control.
    await page.locator('[data-stop-member="4"]').click()
    await expect(page.locator('[data-stop-member="4"]')).to_be_enabled()
    await page.locator('[data-stop-member="4"]').click()
    await expect(page.locator('[data-member="4"] .extm-status')).to_contain_text('已终止')
    await page.locator('[data-member="1"] .extm-toggle').click()
    await expect(page.locator('[data-action="cancel"]')).to_have_text('终止整批')
    await expect(page.locator('.extm-counts')).to_contain_text('已终止 3')
    assert [w[0] for w in fixtures.writes] == [
        '/api/external/members/1/cancel-job', '/api/external/members/2/cancel-job',
        '/api/external/members/4/cancel-job', '/api/external/members/4/cancel-job'], fixtures.writes
    assert fixtures.job['success'] == fixtures.job['fail'] == 1
    assert not errors and not fixtures.escaped, (errors, fixtures.escaped)
    await context.close()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('LIST_BROWSER','chromium')).launch()
        try:
            for prefix in ('','/okad'):
                await scenario(browser, prefix)
        finally:
            await browser.close()
    print('PASS: per-row stop, queued/running/OTP/paused, siblings and completed results, '
          'duplicate/error handling, counts, desktop/mobile/dark, root and /okad')


if __name__ == '__main__':
    asyncio.run(main())
