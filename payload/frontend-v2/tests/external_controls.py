"""Interact with the real Naive UI select menus (no component internals)."""
from playwright.async_api import expect

LABELS = {
    'stock': {'': '全部库存状态', 'false': '未在库', 'true': '在库'},
    'health': {'': '全部 Sub2 状态', '401': '401 · 鉴权失败', '408': '408 · 请求超时', 'other': '其他异常（非 401/408）'},
    'profile': {'': '全部配置', 'personal': '个人配置', 'organization': '组织配置', 'unknown': '未获取'},
    'company': {'': '全部类型', 'true': '公司', 'false': '非公司'},
    'status': {'': '全部状态', 'ok': '正常', 'never': '未登录', 'login_failed': '登录失败'},
    'sub': {'': '全部订阅', 'true': '订阅正常', 'false': '掉订阅'},
    'credits-field': {'available': '可用积分', 'total': '总积分'},

}


def label(selector, value):
    return LABELS[selector.removeprefix('#extm-').removeprefix('f-')][str(value)]


async def select_value(page, selector, value):
    control = page.locator(selector)
    await control.locator('.n-base-selection').click()
    await page.locator('.n-base-select-option:visible').filter(has=page.get_by_text(label(selector, value), exact=True)).click()


async def expect_select(page, selector, value):
    await expect(page.locator(selector).locator('.n-base-selection-label')).to_have_text(label(selector, value))
