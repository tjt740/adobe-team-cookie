#!/bin/bash
# ============================================================
# AdobeTeam 母号管理系统 —— 全新独立部署(空池)
# 在【新服务器】上以 root 运行:  bash install.sh
# 可选环境变量:  ADMIN_USER / ADMIN_PASS(默认 admin / CHANGE_ME)
# ============================================================
set -e
ROOT=/opt/adobeteam
KIT="$(cd "$(dirname "$0")" && pwd)"
export DEBIAN_FRONTEND=noninteractive

echo "=== [1/8] 系统依赖(python venv / nginx) ==="
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx curl ca-certificates >/dev/null
PY=$(command -v python3)
echo "  python3 = $PY ($($PY --version 2>&1))"

echo "=== [2/8] 铺代码到 $ROOT ==="
mkdir -p $ROOT
cp -a "$KIT/payload/." $ROOT/
# 防御:清掉可能混入的缓存/旧库
find $ROOT -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
rm -f $ROOT/backend/app.db 2>/dev/null || true   # 空池:确保全新库

echo "=== [3/8] Python venv + 依赖(pip,约1-3分钟) ==="
cd $ROOT/backend
$PY -m venv .venv
./.venv/bin/pip install --upgrade pip -q
./.venv/bin/pip install -r requirements.txt -q
echo "  依赖装完"

echo "=== [4/8] Playwright 浏览器(母号登录用,首次下载~150MB,较慢) ==="
./.venv/bin/playwright install-deps chromium 2>/dev/null || apt-get install -y -qq $(./.venv/bin/playwright print-deps 2>/dev/null) 2>/dev/null || true
./.venv/bin/playwright install chromium || echo "  ⚠ playwright chromium 安装失败,母号登录前需手动: cd $ROOT/backend && ./.venv/bin/playwright install chromium"

echo "=== [5/8] 写 .env(全新 SECRET_KEY + 管理员) ==="
if [ ! -f $ROOT/backend/.env ]; then
  SK=$($PY -c "import secrets;print(secrets.token_urlsafe(48))")
  AU="${ADMIN_USER:-admin}"; AP="${ADMIN_PASS:-CHANGE_ME}"
  cat > $ROOT/backend/.env <<EOF
SECRET_KEY=$SK
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FIRST_ADMIN_USERNAME=$AU
FIRST_ADMIN_PASSWORD=$AP
FIRST_ADMIN_NICKNAME=超级管理员
CORS_ORIGINS=["http://localhost:5173"]
EOF
  echo "  .env 生成完成 · 管理员: $AU / $AP"
else
  echo "  .env 已存在,保留不动"
fi

echo "=== [6/8] systemd 单元(后端 + 5 定时器) ==="
cp "$KIT"/deploy/systemd/adobeteam*.service "$KIT"/deploy/systemd/adobeteam*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now adobeteam.service
for t in selfheal autopilot pruneorg snapshot reconcile; do
  systemctl enable --now adobeteam-$t.timer 2>/dev/null || echo "  (adobeteam-$t.timer 缺失,跳过)"
done

echo "=== [7/8] nginx(80 端口反代 /api → 8000,静态 frontend-v2) ==="
cp "$KIT/deploy/nginx/adobeteam" /etc/nginx/sites-available/adobeteam
ln -sf /etc/nginx/sites-available/adobeteam /etc/nginx/sites-enabled/adobeteam
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=== [8/8] 验证 ==="
sleep 5
echo "  backend service: $(systemctl is-active adobeteam.service)"
ss -ltnp 2>/dev/null | grep -q :8000 && echo "  8000 监听: OK" || echo "  8000 监听: ✗(查 journalctl -u adobeteam.service)"
echo "  /api/dashboard/overview -> $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/dashboard/overview)  (401=正常,已鉴权)"
echo "  nginx 首页 -> $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/)"
echo ""
echo "============================================================"
echo " 部署完成。浏览器打开  http://<本机公网IP>/"
echo " 登录: ${ADMIN_USER:-admin} / ${ADMIN_PASS:-CHANGE_ME}   (务必进设置改密码)"
echo " 接下来在 UI 里: ①设置→Sub2网关地址+令牌+代理  ②母号管理→导母号  ③邮箱管理→导邮箱"
echo " ⚠ autopilot.conf 里的 BARK_URL 还是源机的,要独立告警请改成你自己的或清空"
echo "============================================================"
