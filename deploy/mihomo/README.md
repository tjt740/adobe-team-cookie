# 线上 Clash 订阅代理

当前接入方式：项目容器 → `mihomo:7890` → 已选择的订阅节点 → Adobe。

## 本地开发

本机也已配置项目独立的 Mihomo。运行 `./start-local.sh` 会自动启动或复用它；打开本地设置页即可更换订阅和节点。它与电脑上已有的 Clash 客户端互不修改配置，也不会同步修改线上订阅。

私有配置和官方 macOS 程序放在 `.local/mihomo-local/`，仅监听 `127.0.0.1:17890`（代理）和 `127.0.0.1:19090`（管理），均带独立认证。不要删除此目录或提交其内容。没有这份本地配置的其他开发环境仍可正常启动项目，并使用原有 HTTP / SOCKS 代理。

网页会读取当前环境的实际配置；本地和线上分别保存订阅。续费同一链接只需刷新，更换链接时应在需要更新的环境分别操作。

Mihomo 与项目使用同一个 Docker 网络，没有公开代理端口或管理端口。项目设置中的代理开关已启用，代理入口认证信息保存在数据库和服务器私有目录。邮箱收码等原本使用直连的流程不会因此全部改走代理。

## 文件与运行方式

在服务器 `/home/admin/adobe-team-cookie` 下：

- `deploy/mihomo/compose.yml`：独立的 Compose 服务，不重建项目容器。
- `deploy/mihomo/manage.py`：订阅、节点管理工具，兼容服务器 Python 3.6。
- `.local/mihomo/config.yaml`：JSON 格式的 Mihomo 配置（JSON 是合法 YAML），含订阅 URL、代理认证和管理密钥，权限 `600`，禁止提交 Git。
- `.local/mihomo/providers/`：订阅节点缓存；也包含凭据，禁止分享。
- `.local/mihomo/backups/`：更换订阅前的私有配置备份。
- `.local/mihomo/application-settings-before.json`：接入前的项目代理设置备份。
- `backups/mihomo-enable-*/app.db`：接入前的数据库备份。

服务自动重启，订阅每小时刷新一次；选择的节点保存在缓存中。主项目执行 `docker compose up -d` 不会管理这个独立服务。

```bash
cd /home/admin/adobe-team-cookie
docker compose -f deploy/mihomo/compose.yml ps
python3 deploy/mihomo/manage.py status
```

## 更换订阅

日常使用直接打开**线上设置 → Clash 订阅代理 → 更换订阅**，粘贴新链接后点击**保存并更新**。页面会展示当前节点、剩余流量及到期时间。选择下拉框中的节点，再点击**切换节点**即可切换出口；续费或想立即同步节点时点击**更新节点**。

页面仅限管理员操作，不会回显订阅链接。保存失败会恢复旧配置；检测到运行中的任务时会拒绝更换。新的订阅若没有旧节点，会提示重新选择。项目代理地址始终不用改。

### 备用命令行方式

先等正在运行的登录任务结束，然后在 SSH 终端执行：

```bash
cd /home/admin/adobe-team-cookie
python3 deploy/mihomo/manage.py update-subscription
```

按提示粘贴新的 **Clash HTTPS 订阅链接**，输入不会回显，也不需要把链接写进 shell 命令历史。工具会备份旧配置、校验配置、重启代理并强制拉取新订阅；失败时恢复旧配置。**项目里的代理地址不用改，项目无需重新部署。**

若新订阅不包含旧节点名称，需要重新选择节点。更新过程会短暂中断代理连接，因此不要在批量登录执行中更换。

如果只是续费，订阅链接没有变，不需要更换链接；等待自动更新或手动刷新：

```bash
python3 deploy/mihomo/manage.py refresh
```

## 查看与切换节点

```bash
python3 deploy/mihomo/manage.py nodes
python3 deploy/mihomo/manage.py select '从上一个命令复制完整节点名称'
python3 deploy/mihomo/manage.py status
```

切换后选一个已有账号重登，确认日志显示 `proxy=有`，且额度查询成功。节点可连接不代表 Adobe 额度接口一定可用；最终应以 Adobe 请求结果为准。不要频繁切换出口或一开始就批量测试全部账号。

## 后续需要注意

- `status` 会显示节点、订阅更新时间、流量用量及到期时间（UTC）。节点名称中的 `x2` 等标记可能表示流量倍率，应以订阅供应商规则为准。
- 订阅链接失效、流量耗尽、节点不可用时，登录和额度查询可能失败；先检查订阅状态与节点，再重试。
- 不要把订阅 URL 填进项目代理地址输入框，也不要把你电脑上的 `127.0.0.1` 代理地址填到线上。
- 不要对公网开放 7890 / 9090，不要向第三方订阅转换网站提交私有链接。
- `.local/mihomo` 应保留，删除它会丢失订阅、代理认证、节点选择缓存。
- 在设置页“Clash 订阅代理”标题右侧开关可立即启用/关闭，无需再点保存。关闭后沿用项目所在机器原有网络（如有环境代理则沿用），保留订阅、节点及私有配置；再次开启自动恢复项目独立代理地址。本地与线上分别生效，线上关闭后使用服务器网络，原有的 Adobe `451` 可能再次出现。
- 运行中、暂停中或尚未终止完成的任务会阻止切换代理，请等任务完成或终止后操作。关闭只影响项目请求，不会关闭电脑上已有的 Clash 客户端。
- 更换服务节点并不改变 Adobe 的服务地区或账号资格要求。

## 安装来源

网页管理通过 `deploy/mihomo/app.override.yml` 为应用挂载私有配置目录，并设置内部控制地址。已部署服务器将它保存为项目根目录的 `compose.override.yml`，日常 `docker compose up -d` 会自动加载。**不要遗漏这个文件**；只复制主 Compose 文件重建服务将导致网页显示未接入。

Mihomo 的 `external-controller` 设置为 `0.0.0.0:9090`，但容器没有任何端口映射，只允许 Docker 内网带密钥访问。应用只暴露受管理员认证保护的订阅/节点接口，没有暴露通用控制接口，也没有挂载 Docker socket。页面更新配置使用官方 [配置重载 API](https://wiki.metacubex.one/api/#configs)，不需要重建项目容器。

当前使用 Mihomo 官方 `v1.19.31` Linux amd64-v1 发布包。由于服务器无法访问 Docker Hub，使用已有应用镜像作为基础镜像，将校验过的官方二进制加入本地镜像 `adobe-mihomo:v1.19.31`；未使用第三方代理镜像。

官方压缩包 SHA-256：`d4304c546c3cddcb6fafd4b4fddb0ba1a95ffa36606fda56d75db2e59ad24114`。

发布来源：https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.31

离线构建上下文 `.local/mihomo-build` 包含官方二进制与校验记录。重建前核对官方发布包摘要，再使用本目录 Dockerfile 构建镜像。升级版本时同时更新 Compose 中的版本标签；不要直接覆盖正在工作的版本。
