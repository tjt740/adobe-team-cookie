# 快速增量发布

发布入口：`python3 deploy/primary/release.py`，仅依赖 Python 标准库和本机 SSH。默认目标为主服务器 `root@173.234.15.150`，使用 `~/.ssh/adobe_primary_ci`；可通过 `--identity` 或 `OKAD_SSH_IDENTITY` 指定密钥文件。

先完成本次变更相关的测试并推送提交，再在干净的工作区发布。`--base` 必须是最近一次实际发布的源码提交；它与当前容器的原始镜像标签可能不同，尤其是此前做过前端免重启发布时。脚本只读取提交内的文件，不携带本地数据库、Cookie、密钥或未提交内容。

```bash
# 只读核验；当前生产应用源码基线为 311bbfb。
python3 deploy/primary/release.py plan --base 311bbfb

# 一个命令完成上传、备份、构建、发布、核验和审计结果下载。
python3 deploy/primary/release.py deploy --base 311bbfb

# 只读测量连接与查询耗时；三次查询共用一条 SSH 连接。
python3 deploy/primary/release.py probe --samples 3
```

`plan` 不在服务器创建目录或修改文件。它读取容器健康状态和源码摘要，核对本次变更文件的宿主与运行时版本；只返回摘要，不下载源码正文。`deploy` 仅传输变更文件和固定发布助手，将目录创建、上传、解包、执行和结果返回合并为一个 SSH 通道。连接主进程显式后台运行，日志文件不占用结果管道；发布进程独立运行，SSH 断开后仍能完成并写入审计。只允许重试连接建立，提交发布后连接中断时先检查原审计的 `exit-code`（0 为结束成功，1 为失败，缺失时查看 `deploy.log`／`worker.pid`），不能自动重放。Docker 构建上下文排除审计、日志与数据库备份。

发布自动选择路径：

- 只有前端 JS、CSS、HTML：保留当前运行容器，先准备可恢复的源码／数据库备份和持久镜像，再更新依赖文件和 HTML，核对实际提供的文件摘要。不等待登录队列，也不重启后端。
- 含后端 `app/` Python 代码：复用已有主机发布保护，确认任务空闲，从实际运行容器快照叠加变更，断网检查语法和应用导入，再只切换 app。保留其他服务、资源设置、用户配置与原账号内容；失败自动回退代码，不恢复旧数据库。
- 已经在线的同一组文件：直接返回 `already_current`，不备份、不构建、不重启。只有文档、测试或发布工具改动时，在本地返回 `no_application_changes`。

依赖、Docker／Compose 配置、数据库模型／初始化、文件删除、二进制资源等变更会明确退出，继续使用专用发布流程。不会把这些变更悄悄漏掉，也不会在运行时与基线冲突或只应用了一部分时覆盖线上内容。此快速入口不替代功能测试；线上通用检查覆盖健康、数据库完整性、账号总数与列表凭据脱敏，本次功能仍应做针对性的页面／接口验收。

本地审计在 `.local/releases/<release>/`；服务器审计在 `/opt/adobe-team-cookie/.local/releases/<release>/`。`result.json` 记录连接、服务器执行、备份、构建、切换和校验耗时。原始完整摘要、配置摘要及备份留在服务器，客户端只接收结果摘要。

回退前，进入服务器审计目录执行 `python3 incremental_remote.py check-rollback`。确认没有后续版本／配置变化，再执行 `python3 incremental_remote.py rollback`；后端回退仍要求任务空闲，前端回退保持容器运行。`already_current` 没有发生切换，无需回退。

本地验证：

```bash
payload/backend/.venv/bin/python -m pytest -q deploy/primary/tests/test_incremental_release.py
```

测试使用临时 Git 仓库、模拟 Docker／HTTP和本地隔离的发布子进程，覆盖增量文件打包、迁移与依赖保护、路径与符号链接、连接管道、断线后继续运行、重复发布、前端免重启、校验失败自动回退、后续配置变化保护和账号内容摘要；不会向生产环境写入业务数据。
