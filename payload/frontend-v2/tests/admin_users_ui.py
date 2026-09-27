"""Admin management interactions against synthetic API responses only."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('ADOBE_TEST_URL', 'http://127.0.0.1:18080')


async def main():
    users = [dict(id=i, username=name, nickname='', is_active=True, is_superuser=True,
                  created_at='2026-09-28T01:00:00Z') for i, name in [(1, 'owner'), (2, 'colleague')]]
    writes = []
    reject = False
    admin = True

    async def api(route):
        req = route.request
        path = urlparse(req.url).path
        data = {'items': [], 'total': 0}
        if path == '/api/auth/me':
            data = {**users[0], 'is_superuser': admin}
        elif path.startswith('/api/admin/users'):
            if req.method == 'GET':
                data = users
            else:
                payload = req.post_data_json
                writes.append((req.method, path, payload))
                await asyncio.sleep(.25)
                if reject:
                    await route.fulfill(status=409, json={'detail': '用户名已存在'})
                    return
                if path == '/api/admin/users':
                    data = dict(id=3, username=payload['username'], nickname=payload['nickname'],
                                is_superuser=True, is_active=True, created_at='2026-09-28T02:00:00Z')
                    users.append(data)
                else:
                    data = next(u for u in users if u['id'] == int(path.split('/')[4]))
                    if req.method == 'PATCH':
                        data.update(payload)
        elif path.endswith('/jobs'):
            data = []
        elif path == '/api/settings':
            data = {'concurrency': 2, 'proxy_enabled': False}
        await route.fulfill(json=data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.route('**/api/**', api)
        await page.add_init_script("localStorage.setItem('okad_token','synthetic-admin-ui-test')")
        await page.goto(BASE + '/settings')
        card = page.locator('#okad-user-management')
        await expect(card.locator('tbody tr')).to_have_count(2)
        await page.locator('.ws-settings-nav').get_by_role('button', name='管理员管理', exact=True).click()
        await expect(card).to_be_in_viewport()
        own = card.locator('[data-user-id="1"]')
        await expect(own.get_by_role('button', name='停用', exact=True)).to_be_disabled()
        await expect(own.get_by_role('button', name='重置密码')).to_be_disabled()
        await card.get_by_role('button', name='新增管理员').click()
        dialog = page.get_by_role('dialog')
        await dialog.get_by_label('用户名').fill('new.admin')
        await dialog.get_by_label('昵称').fill('新同事')
        await dialog.get_by_label('新密码').fill('synthetic-password-123')
        await dialog.get_by_label('确认密码').fill('different-password')
        await dialog.get_by_role('button', name='保存', exact=True).click()
        await expect(dialog.get_by_role('alert')).to_have_text('两次输入的密码不一致')
        assert not writes
        await dialog.get_by_label('确认密码').fill('synthetic-password-123')
        reject = True
        await dialog.get_by_role('button', name='保存', exact=True).click()
        await expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_disabled()
        await expect(dialog.get_by_role('alert')).to_have_text('用户名已存在')
        await expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_enabled()
        reject = False
        await dialog.get_by_role('button', name='保存', exact=True).click()
        await expect(dialog).to_have_count(0)
        await expect(card.locator('tbody tr')).to_have_count(3)
        assert writes[-1] == ('POST', '/api/admin/users', {'username': 'new.admin', 'nickname': '新同事', 'password': 'synthetic-password-123'})
        assert await page.locator('.um-dialog input[type="password"]').count() == 0
        assert 'synthetic-password-123' not in await page.locator('body').inner_text()
        other = card.locator('[data-user-id="2"]')
        await other.get_by_role('button', name='编辑昵称').click()
        await dialog.get_by_label('昵称').fill('同事 <script>')
        await dialog.get_by_role('button', name='保存', exact=True).click()
        await expect(other).to_contain_text('同事 <script>')
        await other.get_by_role('button', name='重置密码').click()
        await dialog.get_by_label('新密码').fill('reset-password-456')
        await dialog.get_by_label('确认密码').fill('reset-password-456')
        await dialog.get_by_role('button', name='保存', exact=True).click()
        await expect(dialog).to_have_count(0)
        assert writes[-1] == ('POST', '/api/admin/users/2/reset-password', {'password': 'reset-password-456'})
        await other.get_by_role('button', name='停用', exact=True).click()
        count = len(writes)
        await dialog.get_by_role('button', name='取消').click()
        assert len(writes) == count
        await other.get_by_role('button', name='停用', exact=True).click()
        await dialog.get_by_role('button', name='确认停用').click()
        await expect(other.get_by_role('button', name='启用', exact=True)).to_be_visible()
        assert writes[-1] == ('PATCH', '/api/admin/users/2', {'is_active': False})
        await other.get_by_role('button', name='启用', exact=True).click()
        await dialog.get_by_role('button', name='确认启用').click()
        await expect(other.get_by_role('button', name='停用', exact=True)).to_be_visible()
        await page.locator('.ws-settings-nav').get_by_role('button', name='管理员管理', exact=True).click()
        await card.screenshot(path=str(Path(__file__).resolve().parents[3] / '.local/admin-users-ui.png'))
        # Route remounts once, and hides privileged actions for legacy non-admins.
        await page.locator('a[href="/adobe"]').click()
        await expect(card).to_have_count(0)
        admin = False
        await page.locator('a[href="/settings"]').click()
        await expect(card).to_have_count(1)
        await expect(card).to_contain_text('仅管理员可以管理登录用户')
        await expect(card.get_by_role('button', name='新增管理员')).not_to_be_visible()
        assert not errors, errors
        await browser.close()
    print('PASS: admin create/edit/reset/disable/enable, self protection, password handling, failures, restricted UI and remount')


if __name__ == '__main__':
    asyncio.run(main())
