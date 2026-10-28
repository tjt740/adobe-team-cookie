# 最后登录时间筛选发布记录

- 上线时间：2026-10-28 11:36:12（上海时间）。
- 入口：<https://creative.cheap/okad/external-members>。
- 功能提交：`28985c88b80f06ae276858596f2c54093f915161`，分支 `codex/okad-last-login-filter`。
- 发布标识：`last-login-filter-20261028013921`。
- 镜像：`adobe-team-cookie:28985c88b80f06ae276858596f2c54093f915161`。

外部子号新增「最后登录时间」起止日期，按列表的 `last_login_at` 筛选，按北京时间包含结束当天，支持只填写一侧、组合其他条件和重置。设置范围后排除没有最后登录时间的账号；分页总数、Cookie 导出及按筛选重登使用相同范围。无需数据库迁移。

在服务器没有活动登录任务、恢复任务、登录租约及同步工作时切换。本次从实际运行镜像增量替换 7 个文件，保留此前生产更新；完整源码摘要确认只有目标文件变化。同机其他服务的容器和镜像保持，原配置、1020 个账号编号、已有 Sub2 关联及 Cookie 版本完整性核验通过。

验证：开发版本与生产源码叠加版本的 52 项相关后端检查通过；合成接口覆盖根路径／`/okad/`、桌面／手机及 Chromium／WebKit。上线后，服务内只读查询确认最后登录列表与 Cookie 导出范围一致、反向区间返回 422、数据库完整性正常。公网 1440px 与 390px 页面日期筛选均匹配 330 个当日账号，北京时间边界及重置正常，无页面错误；未来日期范围返回 0，健康检查正常。未在真实账号上触发测试重登。

审计及备份目录：`/opt/adobe-team-cookie/.local/last-login-filter-20261028013921/`。`before.json`、`after.json`、`last-login-verification.json` 及退出码 0 的 `exit.json` 确认发布完整成功，未触发自动回退。`backup/pre-release.db`、`backup/cutover.db` 保存 SQLite 备份，`backup/payload/` 保存目标文件，另有配置备份。回退镜像：`adobe-team-cookie:before-last-login-filter-20261028013921`；回退前须核对后续发布及配置变化，代码回退不恢复历史数据库。

早先等待任务结束达到 20 分钟上限时，脚本在备份与切换前退出。恢复发布前已重新核对空闲状态、实际容器、运行镜像、运行源码及主机源码；等待记录保存在同一审计目录的 `wait-timeout-deploy.log` 和 `wait-timeout-exit.json`。部署后的 SSH 审计读取曾超时，后续已取回并完成核对。
