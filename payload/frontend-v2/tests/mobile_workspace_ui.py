"""Phone/tablet layout and real touch interactions, using only local assets and synthetic APIs.

Run: payload/backend/.venv/bin/python payload/frontend-v2/tests/mobile_workspace_ui.py
Set MOBILE_BROWSER=webkit to repeat with Playwright's WebKit engine.
"""
import asyncio
import mimetypes
import math
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from external_controls import select_value, expect_select
from playwright.async_api import async_playwright, expect
from jobs_workspace_ui import job

FRONTEND = Path(os.environ.get('OKAD_FRONTEND_DIR', Path(__file__).resolve().parents[1]))
HAS_MONITOR = (FRONTEND / 'server-monitor.js').is_file()
OUTPUT = FRONTEND.parents[1] / '.local' / 'mobile-preview'
ORIGIN = 'http://mobile.test'
EMAIL = 'long.account.' + 'x' * 80 + '@example.test'
PAGES = [('dashboard', '.dash'), ('adobe', '#adobe-workspace'), ('pool', '#pool-workspace'),
         ('email', '#email-workspace'), ('jobs', '#jobs-workspace'), ('logs', '#logs-workspace'),
         ('settings', '.ws-settings-page'), ('external-members', '#extm-embed'),
         ('sub2', '#sub2-panel'), ('server-monitor', '#server-monitor-panel'),
         ('integration', '#integration-panel')]
if not HAS_MONITOR:
    PAGES = [entry for entry in PAGES if entry[0] != 'server-monitor']


def snapshot():
    now = time.time()
    rows = [dict(ts=now-(179-i)*5, cpu=30+15*math.sin(i/12), memory=55+i/30,
                 app_cpu=10+6*math.sin(i/10), app_memory=64+4*math.sin(i/15),
                 rx=10000+7000*math.sin(i/9), tx=23000+12000*math.sin(i/7),
                 rps=2, p95=170+80*math.sin(i/17)) for i in range(180)]
    current = dict(ts=now, service_uptime_seconds=6400,
        host=dict(cpu_percent=38.2, memory_percent=60.4, memory_used=4.83*1024**3,
                  memory_total=8*1024**3, io_wait_percent=1.2, cores=4, load=[1.2,.8,.7],
                  uptime_seconds=2345000, swap_used=0, swap_total=1024**3),
        application=dict(cpu_percent=12, cpu_capacity=4, memory_used=348*1024**2,
                         memory_limit=512*1024**2, memory_percent=68, oom_kills=0, available=True),
        disk=dict(total=100*1024**3, used=42*1024**3, free=58*1024**3, percent=42),
        network=dict(receive_bps=12000, transmit_bps=24000),
        process=dict(memory_rss=150*1024**2, threads=12),
        http=dict(count=120, rps=2, p95_ms=230, active=3, server_errors=0, client_errors=2,
                  error_percent=0, average_ms=95, latency_samples=120),
        jobs=dict(running=2, paused=1, pausing=0, cancelling=0), alerts=[])
    return dict(current=current, history=rows, interval_seconds=5, retention_minutes=60,
                stale=False, age_seconds=1, platform='Linux', container=True)


class Fixtures:
    def __init__(self, prefix):
        self.prefix, self.writes, self.escaped = prefix, [], []
        self.member = dict(id=1, email=EMAIL, login_status='ok', has_cookie=True,
                           credits_available=4000, credits_total=4000, subscription_ok=True,
                           otp_mode='manual', created_at='2026-10-12T00:00:00',
                           note='多行备注\n' + '长文本' * 60)
        self.rows = [dict(self.member, id=i, email=EMAIL if i == 1 else f'mobile{i}@example.test')
                     for i in range(1, 55)]
        self.rows[1]['otp_challenge'] = dict(request_id='a' * 32, email=self.rows[1]['email'],
                                              expires_at=int(time.time()) + 3600)
        self.task = job(77, 'pool_login', email=EMAIL, fail=1)
        self.task['extra']['items'][0]['message'] = 'FailureWithoutSpaces' * 25

    async def serve(self, route):
        req, url = route.request, urlparse(route.request.url)
        if self.prefix and not url.path.startswith(self.prefix + '/'):
            self.escaped.append(url.path)
            return await route.abort()
        path = url.path[len(self.prefix):]
        if not path.startswith('/api/'):
            file = FRONTEND / path.lstrip('/')
            if not file.is_file():
                file = FRONTEND / ('index-okad.html' if self.prefix else 'index.html')
            return await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])
        data = dict(items=[], accounts=[], total=0, ok=True)
        if req.method not in ('GET', 'HEAD'):
            self.writes.append((path, req.post_data_json))
            if path == '/api/external/members/1/note':
                self.rows[0]['note'] = req.post_data_json['note']
                data = self.rows[0]
            else:
                raise AssertionError('Unexpected write: ' + path)
        elif path == '/api/auth/me':
            data = dict(id=1, username='mobile', nickname='很长的管理员名字', is_superuser=True, is_active=True)
        elif path == '/api/dashboard/overview':
            data = dict(admins=dict(valid=1, total=1, type2e=0, dead_org=0),
                        members=dict(full4000=2, building=0, zero=0, cookie=2),
                        capacity=dict(deficit=0, healthy=2, ceiling=4),
                        sub2=dict(ok=True, pending=0, live=2, concurrency=0),
                        emails=dict(unused=1, total=1),
                        health=dict(score=95, grade='健康', alerts=[dict(level='warning', title='测试告警', detail='Error' * 50)]))
        elif path == '/api/monitor/snapshot':
            data = snapshot()
        elif path == '/api/settings':
            data = dict(concurrency=2, proxy_enabled=False)
        elif path == '/api/admin/users':
            data = [dict(id=1, username=EMAIL, nickname='移动端测试', is_active=True, is_superuser=True)]
        elif path == '/api/adobe-accounts':
            data = dict(items=[dict(id=1, email=EMAIL, is_valid=True, has_org=True, member_count=3,
                                   product_name='Firefly', remark='测试团队', refresh_token='synthetic', client_id='synthetic')], total=1)
        elif path == '/api/emails':
            data = dict(items=[dict(id=1, email=EMAIL, password='synthetic', client_id='synthetic',
                                   refresh_token='synthetic', is_used=False, remark='多行\n备注')], total=1)
        elif path == '/api/pool':
            data = dict(items=[dict(id=1, email=EMAIL, status='registered', credits=4000, registered=True,
                                   is_imported=True, has_cookie=True, has_token=True)], total=1)
        elif path == '/api/adobe-accounts/jobs':
            data = [self.task]
        elif path == '/api/adobe-accounts/jobs/77':
            data = self.task
        elif path.startswith('/api/external/members/') and path.endswith('/jobs'):
            data = []
        elif path == '/api/logs':
            data = dict(items=[dict(id=1, time='2026-10-12 12:00:00', level='ERROR', source='test', message='Error' * 200)])
        elif path == '/api/external/members':
            query = parse_qs(url.query)
            page, size = int(query.get('page', ['1'])[0]), int(query.get('size', ['200'])[0])
            data = dict(items=self.rows[(page - 1) * size:page * size], total=len(self.rows))
        elif path == '/api/external/members/2/otp':
            data = dict(challenge=self.rows[1]['otp_challenge'])
        elif path == '/api/external/members/sub2-stock':
            data = dict(ok=True, configured=True, items={})
        elif path == '/api/sub2/config':
            data = dict(admin_token_set=True, base_url='http://sub2.test', platform='adobe', group_ids='2')
        elif path == '/api/sub2/accounts':
            data = dict(ok=True, accounts=[dict(id=1, name=EMAIL, email=EMAIL, platform='adobe', status='active', groups=[])], total=1)
        elif path == '/api/integration/status':
            data = dict(config=dict(base_url='http://sub2.test', enabled=True, key_configured=True, site_id='synthetic'),
                        counts=dict(ready=1), active_jobs=0, jobs=[], checked_at=time.time())
        elif path == '/api/integration/sources':
            data = dict(items=[dict(source='external', source_key='external:1', email=EMAIL,
                                   has_cookie=True, auto_recovery=True, version=1, recovery_message='Reason' * 50,
                                   delivery=dict(state='ready', message='已验证', account_id=1))], total=1)
        await route.fulfill(json=data)


async def fits(page, selector):
    """Check the actual content width, even when an ancestor hides document overflow."""
    await expect(page.locator(selector)).to_be_visible()
    await page.locator(selector).evaluate('''async el => {
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      await Promise.all(el.getAnimations().map(a => a.finished.catch(() => {})));
    }''')
    result = await page.locator(selector).evaluate('''el => {
      const r = el.getBoundingClientRect();
      return {left:r.left, right:r.right, width:innerWidth, overflow:el.scrollWidth-el.clientWidth};
    }''')
    assert result['left'] >= -1 and result['right'] <= result['width'] + 1 and result['overflow'] <= 2, (selector, result)


async def dialog_fits(page, selector):
    # The modal's entrance transform can still be running after a focused input is filled.
    await page.locator(selector).evaluate('(el) => Promise.all(el.getAnimations().map(a => a.finished.catch(() => {})))')
    await fits(page, selector)
    result = await page.locator(selector).evaluate('''el => {
      const r=el.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,height:innerHeight};
    }''')
    assert result['top'] >= -1 and result['bottom'] <= result['height'] + 1, result


async def check(browser, prefix):
    context = await browser.new_context(viewport=dict(width=375, height=812), has_touch=True)
    fixtures, errors = Fixtures(prefix), []
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("if (!location.pathname.endsWith('/login')) localStorage.setItem('okad_token','synthetic-mobile')")
    page = await context.new_page()
    page.set_default_timeout(10000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    base = ORIGIN + prefix
    # Test every content area with populated data, including nested scroll containers.
    for width, height in [(320, 568), (375, 812), (390, 844), (430, 932), (768, 1024), (800, 360), (1440, 1000)]:
        await page.set_viewport_size(dict(width=width, height=height))
        for route, selector in PAGES:
            await page.goto(base + '/' + route)
            await expect(page.locator(selector)).to_be_visible()
            await page.wait_for_timeout(120)
            await fits(page, selector)
            await fits(page, '.n-layout-header')
            if route == 'sub2':
                await fits(page, '.s2-body')
            if route not in ('external-members', 'sub2', 'server-monitor', 'integration'):
                await fits(page, '.n-layout-content.content > .n-layout-scroll-container')
            if width <= 800:
                await expect(page.locator('#okad-mobile-menu')).to_be_visible()
            else:
                await expect(page.locator('#okad-mobile-menu')).to_be_hidden()
        print(f'PASS {prefix or "/"} {width}x{height}: {len(PAGES)} populated pages fit', flush=True)

    await page.set_viewport_size(dict(width=375, height=812))
    # All drawer entries are reachable by touch, including the bottom entry.
    for route, selector in PAGES:
        await page.locator('#okad-mobile-menu').tap()
        await expect(page.locator('.n-layout-sider')).to_have_attribute('aria-modal', 'true')
        link = page.locator('.n-layout-sider a[href="' + prefix + '/' + route + '"]')
        await link.scroll_into_view_if_needed()
        await link.tap()
        await expect(page).to_have_url(base + '/' + route)
        await expect(page.locator('#okad-mobile-menu')).to_have_attribute('aria-expanded', 'false')
        await fits(page, selector)
    # Same-route tap, backdrop, keyboard focus trap, history, and breakpoint cleanup.
    await page.locator('#okad-mobile-menu').tap()
    await page.locator('.n-layout-sider a[href="' + prefix + '/integration"]').tap()
    await expect(page.locator('#okad-mobile-menu')).to_have_attribute('aria-expanded', 'false')
    await page.locator('#okad-mobile-menu').tap()
    await page.keyboard.press('Shift+Tab')
    assert await page.evaluate("document.activeElement.closest('.n-layout-sider') !== null")
    await page.keyboard.press('Escape')
    await expect(page.locator('#okad-mobile-menu')).to_be_focused()
    await page.locator('#okad-mobile-menu').tap()
    await page.locator('#okad-mobile-backdrop').tap(position=dict(x=360, y=100))
    await expect(page.locator('#okad-mobile-backdrop')).to_be_hidden()
    await page.go_back()
    await expect(page.locator(PAGES[-2][1])).to_be_visible()
    await page.locator('#okad-mobile-menu').tap()
    await page.set_viewport_size(dict(width=1440, height=1000))
    await expect(page.locator('[inert]')).to_have_count(0)
    await expect(page.locator('#okad-mobile-backdrop')).to_be_hidden()
    await page.locator('.n-layout-toggle-button').click()
    await expect(page.locator('.n-layout-sider')).to_have_class(re.compile('.*--collapsed.*'))
    await page.set_viewport_size(dict(width=320, height=568))
    await page.locator('#okad-mobile-menu').tap()
    await page.locator('.n-layout-sider a[href="' + prefix + '/adobe"]').tap()
    # Native form dialogs: long values, narrow width, and short keyboard-like viewport.
    await page.get_by_role('button', name='新增账号', exact=True).tap()
    await page.get_by_placeholder('example@hotmail.com').fill(EMAIL)
    await dialog_fits(page, '.n-modal')
    await page.set_viewport_size(dict(width=320, height=360))
    await dialog_fits(page, '.n-modal')
    await page.get_by_role('button', name='取消', exact=True).click()
    await page.set_viewport_size(dict(width=375, height=812))
    # Wide-table operations remain reachable after horizontal scrolling.
    await page.goto(base + '/external-members')
    await expect(page.locator('tr[data-member]')).to_have_count(54)
    await select_value(page, '#extm-page-size', '50')
    await expect(page.locator('tr[data-member]')).to_have_count(50)
    await page.locator('#extm-next').tap()
    await expect(page.locator('tr[data-member]')).to_have_count(4)
    await page.locator('tr[data-member]').last.locator('[data-del]').click(trial=True)
    await page.locator('#extm-first').tap()
    await expect(page.locator('tr[data-member]')).to_have_count(50)
    await page.locator('[data-member="1"] .extm-rowck').check()
    await expect(page.locator('#extm-batch-login')).to_be_enabled()
    await page.locator('[data-note="1"]').click()
    await dialog_fits(page, '#extm-note-dialog')
    await page.locator('#extm-note-dialog textarea').fill('手机编辑\n' + 'LongNote' * 30)
    await page.locator('#extm-note-dialog [type=submit]').tap()
    await expect(page.locator('#extm-note-dialog')).to_have_count(0)
    assert fixtures.writes[0][1]['note'].startswith('手机编辑')
    await page.locator('[data-otp="2"]').click()
    await dialog_fits(page, '#extm-otp-dialog')
    await page.locator('#extm-otp-dialog input').fill('123456')
    await page.locator('#extm-otp-dialog [data-close]').tap()
    await page.set_viewport_size(dict(width=320, height=568))
    await page.locator('#extm-more-actions summary').tap()
    await fits(page, '#extm-more-actions > div')
    await page.keyboard.press('Escape')
    await page.locator('[data-member="1"] .extm-toggle').click()
    await fits(page, '.extm-fold')
    await fits(page, '#extm-embed')
    await page.set_viewport_size(dict(width=375, height=812))
    await page.goto(base + '/jobs?id=77')
    await expect(page.locator('.task-account-row')).to_have_count(2)
    await fits(page, '#jobs-workspace')
    await page.get_by_role('tab', name='执行记录').tap()
    await fits(page, '#jobs-workspace')
    # Settings dialog, popover, search palette, and login are also viewport constrained.
    await page.goto(base + '/settings')
    await page.get_by_role('button', name='新增管理员', exact=True).click()
    await dialog_fits(page, '.um-dialog')
    await page.keyboard.press('Escape')
    await page.locator('.search-trigger').tap()
    await dialog_fits(page, '.cp')
    await page.keyboard.press('Escape')
    await page.locator('.header-right .icon-btn').first.tap()
    await fits(page, '.n-popover')
    await page.keyboard.press('Escape')
    await page.goto(base + ('/server-monitor' if HAS_MONITOR else '/integration'))
    await page.locator('button[title="切换深色"]').tap()
    await expect(page.locator('html')).to_have_class(re.compile('.*dark.*'))
    await fits(page, '#server-monitor-panel' if HAS_MONITOR else '#integration-panel')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(OUTPUT / ('monitor' + ('-mounted' if prefix else '') + '.png')))
    await page.evaluate("localStorage.removeItem('okad_token')")
    await page.goto(base + '/login')
    await page.set_viewport_size(dict(width=320, height=360))
    await fits(page, '.login-page')
    await page.locator('.login-button').click(trial=True)
    assert not fixtures.escaped, fixtures.escaped
    assert not errors, errors
    assert len(fixtures.writes) == 1, fixtures.writes
    await context.close()
    print(f'PASS {prefix or "/"}: touch navigation, focus, history, tables, pagination, dialogs, dark theme, login', flush=True)


async def main():
    async with async_playwright() as p:
        browser = await getattr(p, os.environ.get('MOBILE_BROWSER', 'chromium')).launch()
        try:
            for prefix in ('', '/okad'):
                await check(browser, prefix)
        except Exception:
            OUTPUT.mkdir(parents=True, exist_ok=True)
            for context in browser.contexts:
                for page in context.pages:
                    await page.screenshot(path=str(OUTPUT / 'failure.png'))
            raise
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
