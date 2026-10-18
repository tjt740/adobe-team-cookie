"""Exercise monitoring with synthetic telemetry; no production accounts involved."""
import asyncio
import math
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright, expect

FRONTEND = Path(__file__).resolve().parents[1]
OUTPUT = FRONTEND.parents[1] / '.local' / 'monitor-preview'
ORIGIN = 'http://monitor.test'


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


def business_snapshot(minutes):
    now = time.time()
    rows = [dict(ts=now-(14-i)*60, used=(420+i*12)*1024**2, total=8*1024**3, percent=7) for i in range(15)]
    return dict(status='ok', minutes=minutes, checked_at=now, refresh_seconds=30,
        requests=dict(start=now-minutes*60, end=now, counts=dict(request_count_total=863, success_count=28,
            error_count_total=835, business_limited_count=695), average_rps=2.9, bucket_seconds=60,
            history=[dict(ts=now-(14-i)*60, count=30+i*4) for i in range(15)]),
        memory=dict(current=rows[-1], stale=False, history=rows, samples=15, observed_from=rows[0]['ts'],
            observed_to=rows[-1]['ts'], peak=588*1024**2, minimum=420*1024**2, average=504*1024**2,
            change=168*1024**2))


async def check(browser, prefix):
    context = await browser.new_context(viewport={'width':1440, 'height':1100})
    state = {'fail':False, 'empty':False, 'missing':False, 'hits':0, 'ranges':[], 'cpu':38.2, 'stale':False, 'business':'ok', 'business_ranges':[]}
    errors, escaped = [], []

    async def serve(route):
        parsed = urlparse(route.request.url)
        path = parsed.path
        if prefix and not path.startswith(prefix + '/'):
            escaped.append(path)
            return await route.abort()
        path = path[len(prefix):]
        if path.startswith('/api/'):
            data = dict(items=[], accounts=[], total=0, page=1, ok=True)
            if path == '/api/auth/me':
                data = dict(id=1, username='monitor-test', is_active=True, is_superuser=True)
            elif path == '/api/monitor/snapshot':
                state['hits'] += 1
                state['ranges'].append(parse_qs(parsed.query)['minutes'][0])
                assert route.request.headers.get('authorization') == 'Bearer synthetic-monitor-token'
                if state['fail']:
                    return await route.fulfill(status=503, json={'detail':'Unavailable'})
                data = snapshot()
                data['current']['host']['cpu_percent'] = state['cpu']
                data['stale'] = state['stale']
                if state['empty']:
                    data.update(current=None, history=[], stale=True)
                if state['missing']:
                    data['current']['host']['cpu_percent'] = None
                    for row in data['history']:
                        row['cpu'] = row['app_cpu'] = None
            elif path == '/api/monitor/user-requests':
                minutes = int(parse_qs(parsed.query)['minutes'][0])
                state['business_ranges'].append(minutes)
                data = business_snapshot(minutes)
                if state['business'] == 'zero':
                    data['requests']['counts'] = dict(request_count_total=0, success_count=0, error_count_total=0, business_limited_count=0)
                elif state['business'] == 'stale':
                    data['memory']['stale'] = True
                elif state['business'] == 'forbidden':
                    return await route.fulfill(status=403, json={'detail':'Forbidden'})
                elif state['business'] != 'ok':
                    data = dict(status=state['business'], requests=None, memory={})
            elif path == '/api/settings':
                data = dict(concurrency=2)
            elif path == '/api/adobe-accounts/jobs':
                data = []
            await route.fulfill(json=data)
            return
        file = FRONTEND / path.lstrip('/')
        if not file.is_file():
            file = FRONTEND / ('index-okad.html' if prefix else 'index.html')
        await route.fulfill(path=str(file), content_type=mimetypes.guess_type(file)[0])

    await context.route('**/*', serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-monitor-token')")
    page = await context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    await page.goto(ORIGIN + prefix + '/server-monitor')
    await expect(page.locator('#monitor-cpu-value')).to_have_text('38.2%')
    await expect(page.locator('#server-monitor-nav a')).to_have_attribute('aria-current','page')
    await expect(page.locator('#monitor-cpu-chart svg')).to_have_count(1)
    await expect(page.locator('#monitor-app-detail')).to_contain_text('512 MiB')
    await expect(page.locator('#monitor-http')).to_contain_text('230 ms')
    await expect(page.locator('#monitor-business-counts')).to_contain_text('863 次')
    await expect(page.locator('#monitor-business-memory')).to_contain_text('588 MiB')
    await page.locator('#monitor-business-range').select_option('30')
    await expect(page.locator('#monitor-business-request-chart svg')).to_have_attribute('aria-label', '真实业务请求数量，最近 30 分钟')
    assert state['business_ranges'][-1] == 30
    await page.locator('#monitor-business-range').select_option('15')
    await expect(page.locator('#monitor-business-window')).to_contain_text('最近 15 分钟')
    for mode, expected in [('zero','0 次'), ('unavailable','—'), ('forbidden','—'), ('ok','863 次')]:
        state['business'] = mode
        await page.locator('#monitor-refresh').click()
        await expect(page.locator('#monitor-business-counts article').first.locator('strong')).to_have_text(expected)
    state['business'] = 'stale'
    await page.locator('#monitor-refresh').click()
    await expect(page.locator('#monitor-business-memory article').first.locator('strong')).to_have_text('—')
    await expect(page.locator('#monitor-business-counts')).to_contain_text('863 次')
    state['business'] = 'ok'
    await page.locator('#monitor-refresh').click()
    await expect(page.locator('#monitor-business-memory')).to_contain_text('588 MiB')
    await expect(page.locator('#monitor-health')).to_have_attribute('data-tone', 'good')
    await expect(page.locator('#monitor-score')).to_have_text('99')
    await expect(page.locator('.monitor-explanation')).to_have_count(6)
    await expect(page.locator('#monitor-details p')).to_have_count(8)
    for cpu, level in [(80, 'warn'), (90, 'bad'), (38.2, 'good')]:
        state['cpu'] = cpu
        await page.locator('#monitor-refresh').click()
        await expect(page.locator('#monitor-cpu-value')).to_have_text(str(cpu) + '%')
        await expect(page.locator('#monitor-health')).to_have_attribute('data-tone', level)
        await expect(page.locator('#monitor-cpu-card')).to_have_attribute('data-tone', level)
        colors = await page.evaluate('''() => ['#monitor-cpu-value','#monitor-cpu-state .monitor-badge','#monitor-cpu-bar'].map((s,i) => getComputedStyle(document.querySelector(s))[i===2?'backgroundColor':'color'])''')
        assert len(set(colors)) == 1, colors
    state['stale'] = True
    await page.locator('#monitor-refresh').click()
    await expect(page.locator('#monitor-score')).to_have_text('—')
    await expect(page.locator('#monitor-health')).to_have_attribute('data-tone','unknown')
    state['stale'] = False
    await page.locator('#monitor-refresh').click()
    await expect(page.locator('#monitor-score')).to_have_text('99')
    await page.locator('#monitor-range').select_option('60')
    await expect(page.locator('#monitor-cpu-chart svg')).to_have_attribute('aria-label', 'CPU 使用率，最近 60 分钟')
    assert state['ranges'][-1] == '60'
    await page.locator('#monitor-range').select_option('15')
    await expect(page.locator('#monitor-refresh')).to_be_enabled()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if prefix:
        await page.screenshot(path=str(OUTPUT/'desktop.png'), full_page=True)
    await page.get_by_role('button', name='暂停刷新', exact=True).click()
    before = state['hits']
    await page.wait_for_timeout(5300)
    assert state['hits'] == before
    await expect(page.locator('#monitor-status')).to_have_text('已暂停刷新')
    await expect(page.locator('#monitor-score')).to_have_text('—')
    state['fail'] = True
    await page.get_by_role('button', name='立即刷新', exact=True).click()
    await expect(page.locator('#monitor-notice')).to_contain_text('503')
    await expect(page.locator('#monitor-status')).to_have_text('连接中断')
    await expect(page.locator('#monitor-score')).to_have_text('—')
    await expect(page.locator('#monitor-cpu-value')).to_have_text('38.2%')
    state['fail'], state['missing'] = False, True
    await page.get_by_role('button', name='立即刷新', exact=True).click()
    await expect(page.locator('#monitor-cpu-value')).to_have_text('—')
    await expect(page.locator('#monitor-cpu-chart')).to_contain_text('暂无可用采样')
    state['missing'] = False
    await page.get_by_role('button', name='继续刷新', exact=True).click()
    await expect(page.locator('#monitor-cpu-value')).to_have_text('38.2%')
    await page.get_by_role('link', name='任务中心 →', exact=True).click()
    await expect(page).to_have_url(ORIGIN+prefix+'/jobs')
    await expect(page.locator('#server-monitor-panel')).to_be_hidden()
    before = state['hits']
    await page.wait_for_timeout(5300)
    assert state['hits'] == before
    await page.go_back()
    await expect(page.locator('#server-monitor-panel')).to_be_visible()
    await page.reload()
    await expect(page.locator('#monitor-cpu-value')).to_have_text('38.2%')
    await page.set_viewport_size({'width':780, 'height':1050})
    await page.wait_for_timeout(450)
    overflow = await page.locator('#server-monitor-panel').evaluate('(el) => el.scrollWidth - el.clientWidth')
    assert overflow <= 1, overflow
    if prefix:
        await page.screenshot(path=str(OUTPUT/'compact.png'), full_page=True)
    await page.locator('.monitor-score-method summary').click()
    for width in [320,375,393,430,780,1440]:
        await page.set_viewport_size({'width':width,'height':900})
        await page.wait_for_timeout(450)
        overflow = await page.locator('#server-monitor-panel').evaluate('(el) => el.scrollWidth - el.clientWidth')
        assert overflow <= 1, (width, overflow)
        if prefix and width == 393:
            await page.locator('#monitor-business').scroll_into_view_if_needed()
            await page.screenshot(path=str(OUTPUT/'business-mobile.png'))
            await page.locator('#monitor-health').scroll_into_view_if_needed()
            await page.screenshot(path=str(OUTPUT/'mobile.png'))
    await page.get_by_title("切换深色", exact=True).click()
    await page.wait_for_timeout(450)
    bounds = await page.evaluate("() => ({panel:document.querySelector('#server-monitor-panel').getBoundingClientRect().left,sidebar:document.querySelector('.n-layout-sider').getBoundingClientRect().right})")
    assert abs(bounds['panel'] - bounds['sidebar']) <= 1, bounds
    colors = await page.evaluate('''() => ['#monitor-cpu-value','#monitor-cpu-state .monitor-badge','#monitor-cpu-bar'].map((s,i) => getComputedStyle(document.querySelector(s))[i===2?'backgroundColor':'color'])''')
    assert len(set(colors)) == 1, colors
    if prefix:
        await page.screenshot(path=str(OUTPUT/'dark.png'))
    state['empty'] = True
    await page.reload()
    await expect(page.locator('#monitor-status')).to_have_text('等待第一条采样')
    assert not escaped, escaped
    assert not errors, errors
    await context.close()
    print('PASS', prefix or '/', 'monitor: data, charts, ranges, pause, errors, gaps, navigation, reload, responsive layout, score boundaries, semantic colors, stale score, dark theme', flush=True)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            await check(browser, '/okad')
            await check(browser, '')
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
