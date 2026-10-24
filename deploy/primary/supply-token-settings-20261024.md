# Supply Token 设置发布记录

- 上线时间：2026-10-24 10:40:53（上海时间）。
- 服务器：主服务器 `173.234.15.150`。
- 入口：<https://creative.cheap/okad/settings>。
- 功能提交：`c1aa445cfcba0d13f74c6ab3930e6d77099e174a`；分支 `codex/supply-token-settings`。
- 发布标识：`supply-token-settings-20261024024032`。

项目设置中默认显示 Supply Token 模块，位于 Clash 订阅上方。Token 明文回显，默认中性背景，无说明文字；测试成功显示绿框、SVG 对勾与「token 正常」水印，失败显示红框、SVG 叉号与「token 异常」水印。后端每小时检测并保存结果，页面自动更新；更换或清除 Token 后恢复中性。配置接口要求登录，响应禁止缓存。

发布前，独立分支的 36 项后端测试和根路径／`/okad/` 的桌面、手机四个页面场景通过。部署从实际运行容器增量覆盖八个源码文件，完整源码摘要确认其他运行叠加保留；发布锁、活动任务、配置摘要与数据库备份检查通过，仅重建 Okad app，其他服务保持。

审计和备份目录：`/opt/adobe-team-cookie/.local/supply-token-settings-20261024024032/`，其中 `manifest.json`、`before.json`、`after.json` 记录提交、源码和镜像，`backup/` 保存 SQLite 与原始代码；回退镜像为 `adobe-team-cookie:before-supply-token-settings-20261024024032`。数据库无需结构迁移，定时检测只新增或更新 `supply_mail_health` 配置记录。

公网页面与接口已复核：当前 Token 检测正常，完整回显、SVG 水印、每小时检测时间、匿名拒绝、禁止缓存及桌面／手机布局均通过，无页面错误或额外写入。上线后邮件功能发布叠加为 `adobe-team-cookie:external-mail-reader-20261024T024201Z`，已在该当前运行版本上再次确认本次功能保留。旧版本回滚检查会因后续发布拒绝直接覆盖；需要撤回时应基于最新版本保留后续改动。
