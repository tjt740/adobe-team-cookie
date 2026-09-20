"""Browser regression for the external-account UI using synthetic API responses.

Start start-local.sh, then run with payload/backend/.venv/bin/python.
All /api requests are intercepted; this test never logs into Adobe or alters accounts.
"""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
BASE = os.environ.get("ADOBE_TEST_URL", "http://127.0.0.1:18080")


async def main():
    rows = [{
        "id": i, "email": email, "operator": "admin" if i != 4 else "",
        "created_at": "2026-09-19T05:44:56", "last_login_at": None,
        "has_cookie": i == 2, "has_adobe_password": i != 2,
        "login_status": "login_failed" if i == 1 else "never",
        "subscription_ok": False, "credits_available": None, "credits_total": None,
        "message": '补全账号失败 400: {"errorCode":"invalid_field","errorMessage":"Invalid fields in object completeAccountRequestV2","invalidFieldNames":["account.password"]}' if i == 1 else "",
    } for i, email in enumerate([
        "long.account.name.for.testing@example.com", "design.team@example.com",
        "studio.team@example.com", "new.account@example.com",
    ], 1)]
    jobs = {}
    links = {1: [55, 54, 53], 2: [51], 3: [51], 4: []}
    for jid, ids in [(55, [1]), (54, [1]), (53, [1]), (51, [2, 3])]:
        jobs[jid] = dict(id=jid, type="external_login", operator="admin", status="running" if jid == 51 else "done", target=len(ids), success=0, fail=0 if jid == 51 else 1, created_at=1790000000 + jid, finished_at=None if jid == 51 else 1790000100 + jid, error="", logs=[f"12:00:00 [{rows[ids[0]-1]['email']}] 测试日志 {n}" for n in range(30)], extra={})
    jobs[55]["logs"].extend([
        "12:01:00 任务 #55 完成:成功 1 / 失败 0",
        "12:01:01 警告: 请求超时，正在重试",
        "12:01:02 登录失败: HTTP 400",
        "12:01:03 正在读取邮件…",
        "12:01:04 debug payload <img src=x onerror=alert(1)>",
    ])
    jobs[51]["logs"].append("12:00:01 [studio.team@example.com] 第二个账号日志")
    state = {"posts": 0, "reject": False, "history_error": False, "import_posts": 0, "list_error": False}

    def summary(job, full=False):
        return {**job, "log_total": len(job["logs"]), "logs": job["logs"][:] if full else []}

    async def route_api(route):
        req = route.request
        path = urlparse(req.url).path
        result = {}
        code = 200
        if path == "/api/auth/me":
            result = dict(id=1, username="admin", is_active=True, is_superuser=True)
        elif path == "/api/external/members":
            if state["list_error"]:
                await route.fulfill(status=503, json={"detail": "模拟刷新失败"})
                return
            result = dict(items=[{**r, "latest_job": summary(jobs[links[r['id']][0]]) if links[r['id']] else None} for r in rows], total=len(rows))
        elif path == "/api/external/members/batch-login":
            state["posts"] += 1
            await asyncio.sleep(.5)
            if state["reject"]:
                result, code = {"detail": "模拟提交失败"}, 409
            else:
                ids = req.post_data_json["ids"]
                jid = max(jobs) + 1
                job = dict(id=jid, type="external_login", operator="admin", status="running", target=len(ids), success=0, fail=0, created_at=1790000500, finished_at=None, error="", logs=[f"12:05:00 [{rows[ids[0]-1]['email']}] 开始登录…"], extra={})
                jobs[jid] = job
                for mid in ids:
                    links[mid].insert(0, jid)
                result = summary(job, full=True)
        elif path == "/api/external/members/import":
            state["import_posts"] += 1
            await asyncio.sleep(.3)
            result = dict(created=0, updated=0, skipped=1, failed=0, errors=[])
        elif path.startswith("/api/external/members/") and path.endswith("/jobs"):
            if state["history_error"]:
                result, code = {"detail": "模拟任务网络异常"}, 503
            else:
                result = [summary(jobs[jid]) for jid in links[int(path.split('/')[-2])]]
        elif path == "/api/adobe-accounts/jobs/batch-delete":
            for jid in req.post_data_json["ids"]:
                assert jobs[jid]["status"] != "running"
                for ids in links.values():
                    if jid in ids:
                        ids.remove(jid)
                del jobs[jid]
            result = {"success": True, "message": "已删除任务"}
        elif path.startswith("/api/adobe-accounts/jobs/"):
            segments = path.split('/')
            job = jobs[int(segments[4])]
            if len(segments) > 5:
                if segments[5] == "cancel":
                    job["status"] = "cancelled"
                elif segments[5] == "clear-logs":
                    job["logs"] = []
                result = {"success": True, "message": "操作完成"}
            else:
                result = summary(job, full=True)
        elif path == "/api/sub2/pool-membership":
            result = {"ok": True, "in_sub2": [rows[0]["email"]]}
        elif path == "/api/adobe-accounts/jobs":
            result = [summary(j) for j in jobs.values()]
        elif path == "/api/settings":
            result = {"concurrency": 2}
        else:
            result = {"items": [], "total": 0, "page": 1, "size": 20}
        await route.fulfill(status=code, json=result)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1120}, timezone_id="Asia/Shanghai")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda dialog: dialog.accept())
        await page.route("**/api/**", route_api)
        await page.add_init_script("localStorage.setItem('okad_token', 'synthetic-ui-test')")
        await page.goto(BASE + "/adobe")
        await page.locator("#extm-nav").click()
        await expect(page.locator("tr[data-member]")).to_have_count(4)
        await expect(page.locator('[data-login="2"]')).to_be_disabled()
        await expect(page.locator('[data-login="2"] .extm-spin')).to_be_visible()
        assert await page.locator('.extm-rowck:visible, #extm-ckall:visible').count() == 5
        await page.locator('[data-member="1"] .extm-toggle').click()
        detail = page.locator('#extm-detail-1')
        await expect(detail.locator('.extm-logs')).to_contain_text('测试日志 29')
        await expect(detail.locator('.extm-account-info, .extm-full-message')).to_have_count(0)
        for level, snippet in [("success", "失败 0"), ("warn", "请求超时"), ("error", "HTTP 400"), ("progress", "正在读取"), ("info", "<img src=x")]:
            await expect(detail.locator(f'.extm-logs [data-level="{level}"]').filter(has_text=snippet)).to_have_count(1)
        assert await detail.locator('.extm-logs img').count() == 0
        alignment = await page.locator('[data-member="1"] .extm-toggle').evaluate("button => { const icon=button.querySelector('svg').getBoundingClientRect(), cell=button.closest('td').getBoundingClientRect(); return {dx:Math.abs(icon.x+icon.width/2-cell.x-cell.width/2),dy:Math.abs(icon.y+icon.height/2-cell.y-cell.height/2)}; }")
        assert alignment['dx'] < 1 and alignment['dy'] < 1, alignment
        await expect(page.locator('[data-member="2"] .extm-status')).to_contain_text('有 Cookie')
        await expect(page.locator('[data-member="2"] .extm-status')).to_contain_text('无密码')
        assert await page.locator('[data-detail="1"] > td').evaluate('(node) => getComputedStyle(node).backgroundColor') == 'rgb(242, 242, 242)'
        await expect(detail.locator('.extm-history [data-job]')).to_have_count(3)
        assert await detail.locator('[data-job-check]:visible').count() == 0
        await expect(detail.locator('[data-job="55"] .extm-pill.bad')).to_have_text('失败')
        assert await page.locator('[data-s2stock]').count() == 0
        widths = await page.locator('[data-member="1"]').evaluate("tr => Array.from(tr.cells).map(td => ({w:td.getBoundingClientRect().width,h:td.getBoundingClientRect().height,wrap:getComputedStyle(td).whiteSpace}))")
        assert widths[2]['w'] == 280 and widths[4]['w'] >= 296, widths
        assert all(c['wrap'] == 'nowrap' and c['h'] < 65 for c in widths), widths
        assert '2026-09-19 13:44' in await page.locator('[data-member="1"]').inner_text()
        output = ROOT / '.local'
        output.mkdir(exist_ok=True)
        await page.screenshot(path=str(output / 'inline-task-details-1920.png'), full_page=True)
        # Collapse animates instead of removing the row immediately, and reverses cleanly.
        fold = page.locator('[data-detail="1"] .extm-fold')
        before = (await fold.bounding_box())['height']
        await page.locator('[data-member="1"] .extm-toggle').click()
        await page.wait_for_timeout(70)
        middle = (await fold.bounding_box())['height']
        assert 0 < middle < before, (before, middle)
        await page.locator('[data-member="1"] .extm-toggle').click()
        await expect(page.locator('[data-member="1"] .extm-toggle')).to_have_attribute('aria-expanded', 'true')
        await page.wait_for_timeout(350)
        assert await page.locator('[data-detail="1"]').count() == 1
        await page.locator('[data-member="1"] .extm-toggle').click()
        await expect(page.locator('[data-detail="1"]')).to_have_count(0)
        await page.locator('[data-member="1"] .extm-toggle').click()
        await expect(detail.locator('.extm-logs')).to_contain_text('测试日志 29')
        await page.locator('[data-member="1"] .extm-rowck').check()
        await page.locator('[data-login="1"]').click()
        await expect(page.locator('[data-login="1"]')).to_have_attribute('aria-busy', 'true')
        await expect(page.locator('[data-login="1"]')).to_be_disabled()
        await expect(detail.locator('.extm-logs')).to_contain_text('开始登录')
        await expect(page.locator('[data-login="1"]')).to_contain_text('登录中')
        assert state['posts'] == 1
        await page.locator('#extm-refresh').click()
        await expect(page.locator('[data-member="1"] .extm-rowck')).to_be_checked()
        await expect(detail).to_be_visible()
        await expect(page.locator('[data-login="1"]')).to_be_disabled()
        # Completion and failed outcomes automatically remove the loading state.
        jobs[56].update(status='done', fail=1, finished_at=1790000900)
        jobs[56]['logs'].append('12:05:10 登录失败: 模拟测试')
        await expect(page.locator('[data-login="1"]')).to_be_enabled(timeout=10000)
        await expect(detail.locator('.extm-counts')).to_contain_text('失败 1')
        await expect(detail.locator('.extm-job-title')).to_contain_text('失败')
        assert await detail.locator('.extm-progress').get_attribute('aria-valuenow') == '100'
        # Historical selection and scroll position survive polling.
        await detail.locator('[data-job="55"] button').click()
        await expect(detail.locator('.extm-logs')).to_contain_text('测试日志 29')
        await detail.locator('.extm-logs').evaluate('(node) => { node.scrollTop = 0; }')
        jobs[55]['logs'].append('12:10:00 新日志')
        await expect(detail.locator('.extm-logs')).to_contain_text('新日志', timeout=10000)
        assert await detail.locator('.extm-logs').evaluate('(node) => node.scrollTop') == 0
        # Clear logs and delete a selected historical task without leaving the row.
        await detail.locator('[data-action="clear-logs"]').click()
        await expect(detail.locator('.extm-logs')).to_have_text('暂无日志')
        await detail.locator('[data-action="manage"]').click()
        await detail.locator('[data-job-check="55"]').check()
        await detail.locator('[data-action="delete"]').click()
        await expect(detail.locator('[data-job="55"]')).to_have_count(0)
        await detail.locator('[data-action="manage"]').click()
        assert await detail.locator('[data-job-check]:visible').count() == 0
        # Shared batch task: per-account log filter, whole-job filter and cancellation.
        await page.locator('[data-member="2"] .extm-toggle').click()
        shared = page.locator('#extm-detail-2')
        await expect(shared.locator('.extm-logs')).to_contain_text('design.team')
        await expect(shared.locator('.extm-logs')).not_to_contain_text('第二个账号日志')
        await shared.locator('[data-log-scope]').select_option('all')
        await expect(shared.locator('.extm-logs')).to_contain_text('第二个账号日志')
        await expect(shared.locator('.extm-scope-note')).to_contain_text('整批任务')
        await shared.locator('[data-action="cancel"]').click()
        await expect(page.locator('[data-login="2"]')).to_be_enabled()
        await expect(page.locator('[data-login="3"]')).to_be_enabled()
        # Pausing auto-refresh retains the view; manual refresh works after an error.
        await shared.locator('[data-auto]').uncheck()
        jobs[51]['logs'].append('12:20:00 paused-log')
        await page.wait_for_timeout(3200)
        await expect(shared.locator('.extm-logs')).not_to_contain_text('paused-log')
        state['history_error'] = True
        await shared.locator('[data-action="refresh"]').click()
        await expect(shared.locator(':scope > .extm-detail-error')).to_contain_text('模拟任务网络异常')
        state['history_error'] = False
        await shared.locator('[data-action="refresh"]').click()
        await expect(shared.locator('.extm-logs')).to_contain_text('paused-log')
        # A rejected submission recovers the button, and batches are not submitted empty.
        state['reject'] = True
        await page.locator('[data-login="4"]').click()
        await expect(page.locator('[data-login="4"]')).to_be_enabled(timeout=10000)
        await expect(page.locator('#extm-op')).to_contain_text('模拟提交失败')
        state['reject'] = False
        await page.locator('[data-member="3"] .extm-rowck').check()
        await page.locator('#extm-batch-login').click()
        await expect(page.locator('#extm-batch-login')).to_be_disabled()
        await expect(page.locator('[data-login="3"]')).to_be_disabled()
        await expect(detail.locator('.extm-job-title')).to_contain_text('#57')
        assert jobs[57]['target'] == 2
        # A page reload restores loading from persisted task summaries.
        await page.reload()
        await page.locator('#extm-nav').click()
        await expect(page.locator('[data-login="1"]')).to_be_disabled()
        await expect(page.locator('[data-login="3"]')).to_be_disabled()
        # Import button itself also provides loading feedback.
        await page.locator('#extm-import').fill('synthetic@example.com----test')
        await page.locator('#extm-do-import').click()
        await expect(page.locator('#extm-do-import')).to_have_attribute('aria-busy', 'true')
        await expect(page.locator('#extm-do-import')).to_be_enabled()
        assert state['import_posts'] == 1
        await page.set_viewport_size({'width': 1440, 'height': 1000})
        await page.locator('[data-member="1"] .extm-toggle').click()
        await expect(page.locator('#extm-detail-1 .extm-logs')).to_contain_text('开始登录')
        # Expanded content fits the visible area even though account columns scroll.
        bounds = await page.locator('#extm-detail-1').bounding_box()
        assert bounds['x'] + bounds['width'] <= 1440
        cancel_bounds = await page.locator('#extm-detail-1 [data-action="cancel"]').bounding_box()
        assert cancel_bounds['x'] + cancel_bounds['width'] <= 1440
        await page.locator('.extm-tw').evaluate('(node) => { node.scrollLeft = node.scrollWidth; }')
        bounds = await page.locator('#extm-detail-1').bounding_box()
        assert bounds['x'] >= 220 and bounds['x'] + bounds['width'] <= 1440
        await page.locator('.extm-tw').evaluate('(node) => { node.scrollLeft = 0; }')
        await page.screenshot(path=str(output / 'inline-task-details-1440.png'), full_page=True)
        await page.set_viewport_size({'width': 1100, 'height': 1000})
        await page.wait_for_timeout(200)
        grid = await page.locator('#extm-detail-1 .extm-task-layout').evaluate('(node) => getComputedStyle(node).gridTemplateColumns')
        assert len(grid.split()) == 1, grid
        await page.screenshot(path=str(output / 'inline-task-details-1100.png'), full_page=True)
        await page.emulate_media(reduced_motion='reduce')
        await page.locator('[data-member="1"] .extm-toggle').click()
        await expect(page.locator('[data-detail="1"]')).to_have_count(0)
        await page.locator('[data-member="1"] .extm-toggle').click()
        assert await page.locator('[data-detail="1"] .extm-fold').evaluate('(node) => getComputedStyle(node).transitionDuration') == '0s'
        assert not errors, errors
        await browser.close()
    print('PASS: loading, reload recovery, compact columns, inline history/logs, polling, selection, shared tasks, stop/clear/delete, errors, batch and import')


if __name__ == '__main__':
    asyncio.run(main())
