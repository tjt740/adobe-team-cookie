# 邮箱管理批次与完整格式发布

部署时间：2026-10-24 10:51（北京时间）。入口：<https://creative.cheap/okad/email>。

应用提交：`62a6507046095e349536d6c147137176d36277f9`。分支：`codex/email-management-batches-formats`。版本：`email-management-20261024t024717z`。

此次发布包含批次日期和重复邮箱操作必填、Sub2 在库初始化使用状态、导入批次／导入时间列及批次筛选，以及完整邮箱格式的单条、勾选和筛选全部查看与复制。日期批次为 YYYYMMDD 字符串，实际导入时刻存 UTC，页面显示北京时间；旧记录批次为空，导入时间沿用创建时间。

发布基于运行镜像增量叠加 15 个应用文件，保留既有订阅判定、组织清理、外部邮件阅读和 supply 连接设置等线上改动；其他服务容器、环境配置、原邮箱凭据及使用状态保持。Git 提交仅包含本次邮箱功能，未包含工作区其他未提交工作。

验证通过：仓库候选和生产候选各 19 项后端检查；Chromium／WebKit 桌面和手机、根路径及 /okad/ 的格式复制与导入回归；数据库副本连续两次迁移后 13 张原表的已有字段均不变，402 条旧邮箱可完整读取；切换后检查数据库完整性、接口、批次／重复动作必填以及全部旧邮箱字段和系统设置。公网 1440px、390px 页面核验通过，7 个静态资产摘要及 no-store 缓存策略与发布包一致；公网验证没有提交业务写入，也没有保存实际邮箱凭据截图。

审计目录：`/opt/adobe-team-cookie/.local/email-management-20261024t024717z/`。该目录的 `manifest.json` 保存前后文件摘要、基线容器身份和应用提交，`before.json`／`after.json` 保存切换记录。

备份目录：`/opt/adobe-team-cookie/backups/email-management-20261024t024717z/`，包含 `before.db`、`cutover.db`、原应用文件和 Compose 文件。回滚镜像：`adobe-team-cookie:before-email-management-20261024t024717z`。

只读核对回退条件：

```bash
python3 /opt/adobe-team-cookie/.local/email-management-20261024t024717z/remote_release.py check-rollback
```

仅需恢复本次之前代码时，在核对成功、没有后续发布且任务空闲后执行同一路径的 `rollback`。保留当前业务数据库及新增列，不恢复旧数据库。
