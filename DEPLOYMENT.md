# AdobeTeam 部署与运维

本文档是本项目后续部署到线上 VPS 的标准操作说明。

## 1. 当前线上信息

- SSH 别名：`vps`
- 域名：`manage-adb.example.com`
- 项目目录：`/opt/adobeteam`
- 后端目录：`/opt/adobeteam/backend`
- 前端目录：`/opt/adobeteam/frontend-v2`
- 后端服务：`adobeteam.service`
- 后端监听：`127.0.0.1:8000`
- 公网入口：Caddy `80/443`
- 数据库：`/opt/adobeteam/backend/app.db`
- 后端日志：`journalctl -u adobeteam.service`
- Caddy 配置：`/etc/caddy/Caddyfile`
- Caddy 访问日志：`/var/log/caddy/manage-adb-example-com-access.log`

后端端口只绑定在 `127.0.0.1`，不要把 `8000` 开放到公网或云服务器安全组。公网请求统一经过 Caddy：

```text
浏览器
  -> https://manage-adb.example.com
  -> Caddy
  -> 127.0.0.1:8000/api/*
```

## 2. 重要警告

`install.sh` 是新服务器的空池初始化脚本，里面会删除：

```text
/opt/adobeteam/backend/app.db
```

因此：

- 当前线上更新禁止直接运行 `install.sh`。
- 不要覆盖线上 `.env`。
- 不要删除或覆盖线上 `app.db`。
- 不要使用 `rsync --delete` 同步后端目录，除非已经确认并完成数据库备份。

线上发布使用下面的增量发布流程。

## 3. 发布前检查

在本地项目根目录执行：

```bash
cd /Users/hzbang/Desktop/project/adobeteam_deploy_kit

python3 -m py_compile \
  payload/backend/app/services/job_manager.py \
  payload/backend/app/api/routes/adobe_account.py

node --check payload/frontend-v2/jobs-control-patch.js
```

如果本次修改了其他 Python 文件，把它们一并加入 `py_compile`。

发布前确认工作区没有把用户自己的未提交修改误删。不要使用以下破坏性命令：

```bash
git reset --hard
git checkout -- .
```

## 4. 发布后端

### 4.1 先备份数据库

任务日志、账号、邮箱、配置等数据都在数据库里。发布前先备份：

```bash
ssh vps '
  set -e
  mkdir -p /opt/adobeteam/backups
  cp -a /opt/adobeteam/backend/app.db \
    /opt/adobeteam/backups/app.db.$(date +%Y%m%d-%H%M%S)
'
```

### 4.2 同步后端代码

以下命令不会覆盖线上 `.env`、数据库或虚拟环境：

```bash
rsync -av \
  --exclude '.env' \
  --exclude 'app.db' \
  --exclude 'app.db-*' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  payload/backend/ \
  vps:/opt/adobeteam/backend/
```

如果 `requirements.txt` 有变化，更新依赖：

```bash
ssh vps '
  cd /opt/adobeteam/backend &&
  sudo ./.venv/bin/pip install -r requirements.txt
'
```

### 4.3 编译并重启后端

```bash
ssh vps '
  set -e
  cd /opt/adobeteam/backend
  sudo ./.venv/bin/python -m py_compile \
    app/services/job_manager.py \
    app/api/routes/adobe_account.py
  sudo systemctl restart adobeteam.service
  sleep 3
  test "$(systemctl is-active adobeteam.service)" = active
  curl -fsS http://127.0.0.1:8000/api/health
  echo
'
```

正常结果：

```json
{"status":"ok"}
```

查看后端错误：

```bash
ssh vps 'sudo journalctl -u adobeteam.service -n 200 --no-pager'
```

实时查看：

```bash
ssh vps 'sudo journalctl -u adobeteam.service -f'
```

## 5. 发布前端

Caddy 从 `/opt/adobeteam/frontend-v2` 直接提供前端静态文件。

为了避免 `index.html` 先更新、补丁脚本还没上传，先同步除入口文件外的内容，再最后同步 `index.html`：

```bash
rsync -av \
  --exclude 'index.html' \
  payload/frontend-v2/ \
  vps:/opt/adobeteam/frontend-v2/

rsync -av \
  payload/frontend-v2/index.html \
  vps:/opt/adobeteam/frontend-v2/index.html
```

如果前端有新增或删除构建资源，先确认本地 `payload/frontend-v2` 是完整版本，再考虑使用：

```bash
rsync -av --delete \
  --exclude 'index.html' \
  payload/frontend-v2/ \
  vps:/opt/adobeteam/frontend-v2/

rsync -av \
  payload/frontend-v2/index.html \
  vps:/opt/adobeteam/frontend-v2/index.html
```

`--delete` 只允许用于前端目录，不要用于后端目录。

## 6. 前端强制刷新与缓存

`/etc/caddy/Caddyfile` 已经对以下资源设置了不缓存：

```text
/
/index.html
/*-patch.js
/v2/*
```

每次新增或修改前端补丁脚本时，必须更新 `payload/frontend-v2/index.html` 里的版本号，例如：

```html
<script defer src="/jobs-control-patch.js?v=202607182015"></script>
```

建议使用当前时间生成新版本号：

```text
YYYYMMDDHHmm
```

发布后检查线上是否已经引用新版本：

```bash
curl -sS https://manage-adb.example.com/ | grep -E 'patch.js|assets/index-'
curl -sSI 'https://manage-adb.example.com/jobs-control-patch.js?v=当前版本号'
```

响应头应包含类似：

```text
cache-control: no-cache, no-store, must-revalidate
```

如果浏览器仍显示旧页面，先使用强制刷新：

- macOS：`Cmd + Shift + R`
- Windows/Linux：`Ctrl + Shift + R`

## 7. Caddy 配置

当前站点的核心 Caddy 配置如下。后端端口不能改成公网监听：

```caddyfile
manage-adb.example.com {
    encode gzip zstd

    request_body {
        max_size 50MB
    }

    header {
        -Server
    }

    @adobeteam_no_cache path / /index.html /v2 /v2/ /v2/index.html /*-patch.js /v2/*-patch.js
    header @adobeteam_no_cache Cache-Control "no-cache, no-store, must-revalidate"
    header @adobeteam_no_cache Pragma "no-cache"
    header @adobeteam_no_cache Expires "0"

    handle /api/* {
        reverse_proxy 127.0.0.1:8000 {
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
            flush_interval -1
        }
    }

    handle {
        root * /opt/adobeteam/frontend-v2
        try_files {path} {path}/ /index.html
        file_server
    }
}
```

修改 Caddy 配置后执行：

```bash
ssh vps '
  sudo caddy validate --config /etc/caddy/Caddyfile &&
  sudo systemctl reload caddy &&
  systemctl is-active caddy
'
```

## 8. 任务日志与手动停止

任务记录保存在 SQLite 表 `job_records` 中，后端重启后仍可读取历史任务和日志。

前端操作：

1. 打开 `https://manage-adb.example.com/jobs`
2. 打开正在运行的任务详情
3. 点击“停止任务”
4. 任务状态会变为 `cancelled`，停止日志会保留
5. 日志由用户手动点击“清空日志”

后端停止接口：

```text
POST /api/adobe-accounts/jobs/{job_id}/cancel
```

停止是协作式的：正在执行的网络请求可能需要先返回，任务在下一次取消检查时退出。

紧急情况下可以重启后端，停止所有进程内任务：

```bash
ssh vps 'sudo systemctl restart adobeteam.service'
```

这不会删除数据库里的历史日志，但会让所有正在运行的任务中断。执行后要检查：

```bash
ssh vps '
  systemctl is-active adobeteam.service
  curl -fsS http://127.0.0.1:8000/api/health
  echo
'
```

## 9. 定时任务

线上启用的 systemd 定时器：

```text
adobeteam-selfheal.timer
adobeteam-autopilot.timer
adobeteam-pruneorg.timer
adobeteam-snapshot.timer
adobeteam-reconcile.timer
```

查看状态：

```bash
ssh vps 'systemctl list-timers --all "adobeteam-*" --no-pager'
```

查看某个定时任务最近一次执行：

```bash
ssh vps 'sudo journalctl -u adobeteam-selfheal.service -n 100 --no-pager'
```

如果需要临时暂停自动任务：

```bash
ssh vps '
  sudo systemctl stop adobeteam-autopilot.timer
  sudo systemctl stop adobeteam-selfheal.timer
  sudo systemctl stop adobeteam-reconcile.timer
'
```

恢复：

```bash
ssh vps '
  sudo systemctl start adobeteam-autopilot.timer
  sudo systemctl start adobeteam-selfheal.timer
  sudo systemctl start adobeteam-reconcile.timer
'
```

## 10. 发布后完整验收

```bash
ssh vps '
  set -e
  test "$(systemctl is-active adobeteam.service)" = active
  test "$(systemctl is-active caddy)" = active
  curl -fsS http://127.0.0.1:8000/api/health
  echo
'

curl -fsS https://manage-adb.example.com/ >/dev/null
curl -fsS https://manage-adb.example.com/jobs-control-patch.js >/dev/null
```

同时确认端口监听：

```bash
ssh vps 'ss -ltnp | grep -E ":80|:443|:8000" || true'
```

预期：`8000` 只监听 `127.0.0.1`，不能出现 `0.0.0.0:8000`。

## 11. 回滚

代码回滚应使用本地已确认可用的上一版本重新 `rsync`，然后重启后端。

数据库回滚前必须先停止后端并确认备份文件：

```bash
ssh vps '
  set -e
  sudo systemctl stop adobeteam.service
  ls -lh /opt/adobeteam/backups/
  cp -a /opt/adobeteam/backend/app.db \
    /opt/adobeteam/backups/app.db.before-restore.$(date +%Y%m%d-%H%M%S)
  cp -a /opt/adobeteam/backups/app.db.具体时间 \
    /opt/adobeteam/backend/app.db
  sudo systemctl start adobeteam.service
'
```

不要在没有明确备份文件名的情况下执行数据库恢复。

## 12. 新服务器初始化

只有在全新、允许清空数据的服务器上才使用：

```bash
sudo bash install.sh
```

该脚本当前默认安装 Nginx，而现有线上环境使用 Caddy。若新服务器要求与线上一致，应在初始化后：

1. 停止并移除 Nginx 的占用。
2. 安装并配置 Caddy。
3. 使用本文件第 7 节的站点配置。
4. 确认后端仍只监听 `127.0.0.1:8000`。
5. 配置域名 DNS 和 TLS。

新服务器初始化完成后，仍然要修改管理员密码、配置 Sub2、自建号池和代理，并检查定时任务是否符合预期。

## 外部子号管理

独立于「号池(adobe_members)」的模块,用于导入外部企业子号、协议登录拿 cookie,并对外提供按需刷新 cookie 的接口。

- **页面**:登录后侧边栏「外部子号管理」(前端 `external-members-patch.js` 运行时注入)。
- **导入格式**:每行 `邮箱----密码----ClientID----RefreshToken`(密码/ClientID/RefreshToken 均为**微软邮箱** OAuth 凭据,用于收 Adobe 验证码;复用 `_parse_email_line`,亦兼容 `|` 分隔与字段乱序)。
- **列表字段**:邮箱、积分(可用/总量,如 `4000/4000`)、登录状态、是否掉订阅(配额总量 < 1000 判掉),可按登录状态 / 订阅状态筛选。
- **对外接口**:`POST /api/v1/adobe/cookie/refresh`,鉴权 `X-API-Key`(设置页 `external_api_key`),契约见 `self-cookie-provider-api.md`。每次调用**无条件重新登录**该邮箱,拿到最新 cookie 后**同时存库并返回**;业务失败一律 `200 + {ok:false, code}`,仅传输层错误用 401/400/5xx。
- **代理**:设置页 `external_proxy_url`(每行一个,支持大量条目,已做 split 缓存);每次登录随机取一个出口。
- **cookie 刷新时机**:①导入后「批量登录」任务 ②对外接口被调用时 ③列表「重登」按钮。**无定时心跳**,列表中的积分/状态是该号最后一次登录时的快照。

### 对外接口自测

设置页填好 `external_api_key` 后:

```bash
# 期望 200 + ok:false + code=account_disabled(库中无此邮箱时)
curl -sS -X POST 'http://<host>/api/v1/adobe/cookie/refresh' \
  -H 'Content-Type: application/json' -H 'X-API-Key: <key>' \
  -d '{"email":"user@example.com"}'
```

错 key → 401;缺 email / 非法 JSON → 400;库中存在的邮箱 → 200 + ok:true + 非空 cookie。
