"""Visible profile fallback reasons, escaping, refresh and both deployment paths."""
import asyncio
import copy
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect
from mobile_workspace_ui import Fixtures

OUTPUT = Path(__file__).resolve().parents[3] / '.local' / 'invited-profile-preview'
TEAM = 'NOvA <测试>'
REASON = '组织「' + TEAM + '」邀请激活失败（HTTP 403）'


class ProfileFixtures(Fixtures):
    async def serve(self, route):
        path = urlparse(route.request.url).path.removeprefix(self.prefix)
        if path == '/api/external/groups':
            return await route.fulfill(json=[])
        if path == '/api/external/members/sub2-stock':
            return await route.fulfill(json=dict(ok=True, configured=True, items={
                1: dict(email=self.rows[0]['email'], in_stock=False, account_ids=[])}))
        return await super().serve(route)


async def scenario(browser, prefix, mobile):
    fixtures, errors = ProfileFixtures(prefix), []
    profile = dict(current_kind='personal', account_type='type1',
                   current_profile_id='personal@AdobeID', current_profile_name='Personal Account',
                   current_org_id='', credits_account_id='personal@AdobeID',
                   profiles_complete=True, requested_preference='organization', fallback_reason=REASON,
                   fetched_at='2026-10-20T06:00:00Z', profiles=[
                       dict(profile_id='personal@AdobeID', name='Personal Account', kind='personal', status='active'),
                       dict(profile_id='member@team.e', name=TEAM, kind='organization', status='invited')])
    fixtures.rows = [dict(fixtures.member, account_profile=profile, profile_preference='organization')]
    context = await browser.new_context(viewport={'width':390 if mobile else 1600, 'height':1000},
                                        is_mobile=mobile, has_touch=mobile, timezone_id='Asia/Shanghai')
    await context.route('**/*', fixtures.serve)
    await context.add_init_script("localStorage.setItem('okad_token','synthetic-profile-fallback')")
    if mobile:
        await context.add_init_script("localStorage.setItem('okad-theme','dark')")
    page = await context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        await page.goto('http://profile.test' + prefix + '/external-members')
        row = page.locator('tr[data-member="1"]')
        badge = row.locator('[data-profile-fallback]')
        await expect(badge).to_have_text('已回退个人')
        await expect(badge).to_have_attribute('title', REASON)
        overflow = await row.locator('.extm-profile-toggle').evaluate('el => el.scrollWidth - el.clientWidth')
        assert overflow <= 1, overflow
        await row.locator('.extm-toggle').click()
        detail = page.locator('#extm-detail-1 .extm-profile-card')
        reason = detail.locator('.extm-profile-fallback-reason')
        await expect(reason).to_have_text('回退个人配置原因：' + REASON)
        await expect(detail).to_contain_text('本次登录选择：组织配置优先')
        await expect(detail).to_contain_text('邀请待激活')
        assert await detail.locator('测试').count() == 0, 'Profile metadata must be escaped as text'
        filename = ('mobile-dark' if mobile else 'desktop') + ('-okad.png' if prefix else '.png')
        await reason.scroll_into_view_if_needed()
        await page.screenshot(path=str(OUTPUT / filename), animations='disabled')
        overflow = await reason.evaluate('el => el.scrollWidth - el.clientWidth')
        assert overflow <= 1, overflow

        updated = copy.deepcopy(profile)
        updated.update(current_kind='organization', account_type='type2e',
                       current_profile_id='member@team.e', current_profile_name=TEAM,
                       current_org_id='team@AdobeOrg', credits_account_id='member@team.e', fallback_reason='')
        updated['profiles'][1]['status'] = 'active'
        fixtures.rows[0]['account_profile'] = updated
        await page.locator('#extm-refresh').click()
        await expect(row.locator('[data-profile-fallback]')).to_have_count(0)
        await expect(detail.locator('.extm-profile-fallback-reason')).to_have_count(0)
        await expect(detail.locator('.extm-profile-fields')).to_contain_text(TEAM)
        await expect(detail).not_to_contain_text('邀请待激活')
        assert fixtures.writes == [] and fixtures.escaped == []
        assert not errors, errors
    finally:
        await context.close()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await getattr(playwright, os.environ.get('PROFILE_BROWSER', 'chromium')).launch()
        try:
            for prefix in ('', '/okad'):
                for mobile in (False, True):
                    await scenario(browser, prefix, mobile)
        finally:
            await browser.close()
    print('PASS: visible fallback reasons, escaped metadata, successful refresh clears warning, desktop/mobile/dark, root and /okad')


if __name__ == '__main__':
    asyncio.run(main())
