#!/bin/bash
set -euo pipefail

# 实验室物料库存管理系统 - 阿里云部署脚本
# 前端源码统一维护在 frontend/ 目录。

APP_DIR="/opt/lab-inventory"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$APP_DIR/backups/$(date +%Y%m%d-%H%M%S)"

echo "=========================================="
echo "开始部署实验室物料库存管理系统"
echo "=========================================="

echo "[1/6] 安装运行依赖..."
if command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 python3-pip nginx
else
    yum install -y python3 python3-pip nginx
fi

echo "[2/6] 备份旧版本..."
mkdir -p "$BACKUP_DIR"
if [ -d "$BACKEND_DIR" ]; then
    cp -a "$BACKEND_DIR" "$BACKUP_DIR/backend"
fi
if [ -d "$FRONTEND_DIR" ]; then
    cp -a "$FRONTEND_DIR" "$BACKUP_DIR/frontend"
fi

echo "[3/6] 同步完整项目文件..."
mkdir -p "$BACKEND_DIR" "$FRONTEND_DIR"
rsync -a --delete \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude "logs/" \
    "$SCRIPT_DIR/backend/" "$BACKEND_DIR/"

rsync -a --delete "$SCRIPT_DIR/frontend/" "$FRONTEND_DIR/"
rm -f "$FRONTEND_DIR/dashboard.html"

mkdir -p "$BACKEND_DIR/logs" "$BACKEND_DIR/uploads"

echo "[4/6] 安装 Python 依赖并初始化数据..."
cd "$BACKEND_DIR"
pip3 install -r requirements.txt
python3 init_data.py

echo "[5/6] 配置 Nginx..."
cat > /etc/nginx/conf.d/lab-inventory.conf <<'EOF'
server {
    listen 80 default_server;
    server_name _;

    root /opt/lab-inventory/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /uploads/ {
        alias /opt/lab-inventory/backend/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }
}
EOF

rm -f /etc/nginx/conf.d/default.conf

echo "[6/6] 重启服务..."
pkill -f "$BACKEND_DIR/run.py" 2>/dev/null || true
pkill -f "python3 -m http.server 80" 2>/dev/null || true
cd "$BACKEND_DIR"
FLASK_CONFIG=production nohup python3 run.py > logs/app.log 2>&1 &

nginx -t
systemctl enable nginx >/dev/null 2>&1 || true
systemctl restart nginx || nginx

echo ""
echo "=========================================="
echo "部署完成"
echo "=========================================="
echo "登录页面: http://8.166.118.116"
echo "后端健康检查: http://8.166.118.116/api/health"
echo "默认账号: admin / admin"
echo "备份目录: $BACKUP_DIR"
echo "项目目录: $APP_DIR"
echo "日志文件: $BACKEND_DIR/logs/app.log"
echo "=========================================="
