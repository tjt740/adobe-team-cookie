"""Interact with the real Naive UI select menus (no component internals)."""
from playwright.async_api import expect

LABELS = {
    'stock': {'': '全部库存状态', 'false': '未在库', 'true': '在库'},
    'health': {'': '全部 Sub2 状态', 'error': '全部异常', '401': '401 · 鉴权失败', '408': '408 · 请求超时', '403':'403', '429':'429 · 限流', '500':'500', '502':'502', '503':'503', '504':'504', '529':'529 · 过载', 'other':'其他异常（非 401/408）', 'recovered':'已有成功证据', 'unknown':'待验证 / 无完整记录'},
    'sync': {'': '全部同步状态', 'pending': 'Sub2 待同步', 'syncing': 'Sub2 同步中',
             'synced': 'Sub2 已同步', 'failed': 'Sub2 同步失败', 'not_pushed': 'Sub2 未推送'},
    'profile': {'': '全部配置', 'personal': '个人配置', 'organization': '组织配置', 'unknown': '未获取'},
    'company': {'': '全部类型', 'true': '公司', 'false': '非公司'},
    'status': {'': '全部状态', 'ok': '正常', 'never': '未登录', 'login_failed': '登录失败'},
    'sub': {'': '全部订阅', 'true': '订阅正常', 'false': '掉订阅'},
    'credits-field': {'available': '可用积分', 'total': '总积分'},
    'otp-mode': {'': '保留设置（新账号自动取码）', 'auto': '自动取码（supply.ink）', 'manual': '手动输入验证码（普通账号）'},
    'dup': {'skip': '跳过', 'overwrite': '覆盖'},
}


def label(selector, value):
    if selector == '#extm-page-size':
        return str(value) + ' 条'
    return LABELS[selector.removeprefix('#extm-').removeprefix('f-')][str(value)]


async def select_value(page, selector, value):
    control = page.locator(selector)
    await control.locator('.n-base-selection').click()
    option = page.locator('.n-base-select-option:visible').filter(has=page.get_by_text(label(selector, value), exact=True))
    await expect(option).to_have_count(1)
    await option.click()


async def expect_select(page, selector, value):
    await expect(page.locator(selector).locator('.n-base-selection-label')).to_have_text(label(selector, value))


async def set_import_dates(page, start=None, end=None):
    dialog = page.locator('#extm-import-date-dialog')
    if not await dialog.is_visible():
        await page.locator('#extm-f-import-range').click()
    if start is not None:
        await dialog.locator('#extm-f-import-from').fill(start)
    if end is not None:
        await dialog.locator('#extm-f-import-to').fill(end)
    await dialog.locator('#extm-date-apply').click()
