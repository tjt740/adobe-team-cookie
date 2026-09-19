# Adobe Team Cookie

Adobe 母号、子号与 Cookie 管理平台，FastAPI + SQLite + 预构建 Web 界面。

## 当前生产部署

- 地址：http://47.106.176.71:9500
- 目录：`/home/admin/adobe-team-cookie`
- 运行方式：Docker Compose，开机自动恢复
- 数据库：`data/app.db`，升级保留
- 管理员：`admin`，首次随机密码见服务器 `.env` 的 `FIRST_ADMIN_PASSWORD`

```bash
python3 deploy/init-env.py
docker compose up -d --build
curl --fail http://127.0.0.1:9500/api/health
```

若服务器无法访问 Docker Hub，可在构建机执行 `docker build --platform linux/amd64 -t adobe-team-cookie:latest .`，通过 `docker save` / `docker load` 传输，再执行 `docker compose up -d --no-build`。

更新前使用 SQLite backup 备份 `data/app.db`。发布代码时保留 `.env`、`data/` 和 `backups/`；不要运行旧的 `install.sh`，它是原始部署包的空池安装器。原始部署方案保留在 `DEPLOYMENT.md`，与本次容器部署不同。

本地账号库、Cookie、浏览器档案和密钥不上传 GitHub，生产环境首次为空库。原始自动删号/补号定时器未自动启用；需要时应先配置并检查其行为。

```bash
docker compose ps
docker compose logs --tail=100 app
```
