# 外部子号精确时间与排序发布记录

- 上线时间：2026-10-29 09:34:54（上海时间）。
- 入口：<https://creative.cheap/okad/external-members>。
- 功能提交：`e8938b4a20425a83556c4f9d14adaffa0b437904`，分支 `codex/external-time-sort`。
- 发布标识：`external-time-sort-20261028185658`。
- 镜像：`adobe-team-cookie:e8938b4a20425a83556c4f9d14adaffa0b437904`。
- 镜像 ID：`sha256:a028b8dbe026bd82a986cdcee1bb2fb5dcaac1c1866d616b15a596970bf231e8`。

外部子号移除「账号状态」筛选；导入时间和最后登录时间使用北京时间的日期、时分秒，支持单侧范围、包含结束秒及重置。列表和展开详情显示到秒，新增导入时间列，两个时间表头支持正序／倒序，手机提供对应排序按钮。服务端先排序再分页，空登录时间末尾、同时间按账号编号稳定排列；Cookie 导出和按筛选重登共享范围与排序。无需数据库迁移。

遵循等待现有任务完成的要求，在登录、恢复、租约和内部同步全部空闲后启动发布，未中断原任务。发布前重新核对实际容器、镜像、运行源码和主机源码；从当时运行容器捕获回退镜像，在其上只替换以下 8 个文件，保留此前生产更新：

- `backend/app/api/routes/external_member.py`
- `backend/app/crud/external_member.py`
- `backend/app/schemas/external_member.py`
- `frontend-v2/external-members-patch.js`
- `frontend-v2/external-members-view.js`
- `frontend-v2/external-members-view.css`
- `frontend-v2/index.html`
- `frontend-v2/index-okad.html`

完整运行源码摘要确认只有这 8 个文件发生变化。只切换 Okad app；同机其他服务（包括 Sub2）的容器和镜像保持，除 Compose 镜像引用外的配置保持。SQLite 完整性、1021 个既有账号编号、原业务设置、Sub2 固定关联和 Cookie 版本归属核验通过。

开发源码与生产源码叠加版本均通过 67 项相关后端检查。合成浏览器检查覆盖 Chromium／WebKit、根路径／`/okad/`、桌面／手机。上线后的服务内只读检查确认两个时间字段双向排序、同秒导入范围、Cookie 导出范围和非法排序参数拒绝均正常。公网 1440px 与 390px 验收确认无账号状态筛选、4 个 `step=1` 时间控件、导入列、双向排序、北京时间同秒范围及重置正常，页面错误和非预期写请求均为 0；未在真实账号上发起测试重登。可公开的验证摘要见 [验收证据](external-time-sort-verification-20261029.json)。

远端审计与备份目录：`/opt/adobe-team-cookie/.local/external-time-sort-20261028185658/`。`before.json`、`after.json`、`time-sort-verification.json` 和退出码 0 的 `exit.json` 确认发布成功，未触发自动回退。`backup/pre-release.db`、`backup/cutover.db` 为 SQLite 备份，`backup/payload/` 保存原目标文件，目录内另有配置备份及 `remote-deploy.log`。

本地验收目录：`/Users/t/Documents/ChatGPT/adobe-team-cookie/.local/external-time-sort-20261029/`，包含上述审计副本、`release-validation.json`、`public-verification.json` 及桌面／手机截图。SSH 连接曾间歇超时；重新只读核对未启动状态后，守护进程成功启动一次，未重复执行部署。

回退镜像：`adobe-team-cookie:before-external-time-sort-20261028185658`，ID `sha256:5c67421ce0d1b12828acf0a741ccb48941d06673c46ef941db7c4c036eb24f3e`。回退前须核对后续发布、配置和当前任务状态；代码回退保留当前业务数据，禁止恢复历史数据库。
