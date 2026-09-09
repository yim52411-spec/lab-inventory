# 实验室物料库存管理系统 - 云服务器部署指南

## 部署方案概览

本系统支持以下部署方式：
1. **Docker Compose 一键部署**（推荐）
2. **手动部署**

## 方案一：Docker Compose 一键部署（推荐）

### 1. 购买阿里云服务器

**推荐配置：**
- **ECS 实例**：2核4G 或更高
- **操作系统**：Ubuntu 22.04 LTS 或 CentOS 8
- **带宽**：5Mbps 或更高
- **存储**：40GB SSD 或更高
- **安全组**：开放 80、443、22 端口

### 2. 连接服务器

```bash
# 使用 SSH 连接服务器
ssh root@your-server-ip
```

### 3. 安装 Docker 和 Docker Compose

```bash
# 更新系统
apt-get update && apt-get upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 启动 Docker
systemctl start docker
systemctl enable docker

# 安装 Docker Compose
apt-get install docker-compose -y

# 验证安装
docker --version
docker-compose --version
```

### 4. 上传项目文件

**方式1：使用 Git**
```bash
# 在服务器上克隆项目
git clone your-repository-url /opt/lab-inventory
cd /opt/lab-inventory
```

**方式2：使用 SCP**
```bash
# 在本地终端执行
scp -r /path/to/lab-inventory root@your-server-ip:/opt/
ssh root@your-server-ip
cd /opt/lab-inventory
```

### 5. 修改配置文件

#### 修改 docker-compose.yml

```bash
# 编辑配置文件
nano docker-compose.yml
```

**需要修改的地方：**
- `MYSQL_ROOT_PASSWORD`: MySQL root 密码
- `MYSQL_PASSWORD`: MySQL 用户密码
- `DATABASE_URL`: 数据库连接字符串中的密码
- `SECRET_KEY`: Flask 密钥（使用随机字符串）
- `JWT_SECRET_KEY`: JWT 密钥（使用随机字符串）
- `MAIL_USERNAME`: 邮箱地址
- `MAIL_PASSWORD`: 邮箱密码

**生成随机密钥：**
```bash
# 生成 32 位随机字符串
openssl rand -base64 32
```

#### 修改 Nginx 配置

```bash
nano nginx.conf
```

**需要修改的地方：**
- `server_name`: 你的域名
- `ssl_certificate`: SSL 证书路径
- `ssl_certificate_key`: SSL 密钥路径

### 6. 配置域名和 SSL 证书

#### 方式1：使用 Let's Encrypt（免费）

```bash
# 安装 Certbot
apt-get install certbot python3-certbot-nginx -y

# 获取证书（替换为你的域名）
certbot --nginx -d your-domain.com -d www.your-domain.com

# 自动续期
systemctl enable certbot.timer
```

#### 方式2：使用阿里云 SSL 证书

1. 在阿里云控制台购买/申请 SSL 证书
2. 下载 Nginx 格式的证书
3. 上传到服务器 `/etc/nginx/ssl/` 目录
4. 修改 `nginx.conf` 中的证书路径

### 7. 启动服务

```bash
# 进入项目目录
cd /opt/lab-inventory

# 创建必要目录
mkdir -p backend/logs backend/uploads ssl

# 启动服务（后台运行）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 8. 初始化数据库

```bash
# 进入后端容器
docker-compose exec backend bash

# 初始化数据库
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 创建管理员账号
python init_data.py

# 退出容器
exit
```

### 9. 访问系统

- **前台地址**：https://your-domain.com
- **默认账号**：
  - 管理员：admin / admin
  - 访问者：visitor / visitor

---

## 方案二：手动部署

### 1. 安装依赖

```bash
# 更新系统
apt-get update

# 安装 Python 3.9
apt-get install python3.9 python3.9-pip python3.9-venv -y

# 安装 MySQL
apt-get install mysql-server -y

# 安装 Nginx
apt-get install nginx -y

# 安装其他依赖
apt-get install gcc default-libmysqlclient-dev pkg-config -y
```

### 2. 配置 MySQL

```bash
# 登录 MySQL
mysql -u root -p

# 创建数据库和用户
CREATE DATABASE lab_inventory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'lab_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON lab_inventory.* TO 'lab_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. 部署后端

```bash
# 创建目录
mkdir -p /opt/lab-inventory
cd /opt/lab-inventory

# 上传后端代码
# ... 使用 git clone 或 scp ...

# 创建虚拟环境
python3.9 -m venv venv
source venv/bin/activate

# 安装依赖
cd backend
pip install -r requirements.txt
pip install gunicorn gevent pymysql

# 配置通过环境变量注入，不直接修改代码中的配置文件

# 设置环境变量
export FLASK_APP=run.py
export FLASK_CONFIG=production
export DATABASE_URL="mysql+pymysql://lab_user:your_password@localhost:3306/lab_inventory?charset=utf8mb4"
export SECRET_KEY="your-secret-key"
export JWT_SECRET_KEY="your-jwt-secret-key"

# 初始化数据库
flask db init
flask db migrate
flask db upgrade
python init_data.py

# 启动 Gunicorn
gunicorn -c gunicorn.conf.py run:app
```

### 4. 配置 Systemd 服务

创建服务文件 `/etc/systemd/system/lab-inventory.service`：

```ini
[Unit]
Description=Lab Inventory System
After=network.target mysql.service

[Service]
User=root
WorkingDirectory=/opt/lab-inventory/backend
Environment="PATH=/opt/lab-inventory/venv/bin"
Environment="FLASK_APP=run.py"
Environment="FLASK_CONFIG=production"
Environment="DATABASE_URL=mysql+pymysql://lab_user:your_password@localhost:3306/lab_inventory?charset=utf8mb4"
Environment="SECRET_KEY=your-secret-key"
Environment="JWT_SECRET_KEY=your-jwt-secret-key"
ExecStart=/opt/lab-inventory/venv/bin/gunicorn -c gunicorn.conf.py run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
systemctl daemon-reload
systemctl enable lab-inventory
systemctl start lab-inventory
systemctl status lab-inventory
```

### 5. 配置 Nginx

```bash
# 复制配置文件
cp /opt/lab-inventory/nginx.conf /etc/nginx/sites-available/lab-inventory

# 修改配置文件中的域名和路径
nano /etc/nginx/sites-available/lab-inventory

# 启用站点
ln -s /etc/nginx/sites-available/lab-inventory /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# 测试配置
nginx -t

# 重启 Nginx
systemctl restart nginx
```

### 6. 部署前端

```bash
# 创建前端目录
mkdir -p /var/www/lab-inventory

# 复制前端文件
cp -r /opt/lab-inventory/frontend/* /var/www/lab-inventory/

# 修改 API 地址
nano /var/www/lab-inventory/api.js
# 将 API_BASE_URL 修改为 '/api'
```

---

## 日常维护

### 查看日志

```bash
# Docker 方式
docker-compose logs -f backend
docker-compose logs -f nginx

# 手动方式
journalctl -u lab-inventory -f
tail -f /opt/lab-inventory/backend/logs/error.log
```

### 备份数据

```bash
# 备份 MySQL 数据库
mysqldump -u lab_user -p lab_inventory > backup_$(date +%Y%m%d).sql

# 备份上传文件
tar -czvf uploads_backup_$(date +%Y%m%d).tar.gz /opt/lab-inventory/backend/uploads/
```

### 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动（Docker 方式）
docker-compose down
docker-compose up -d --build

# 手动方式
systemctl restart lab-inventory
```

---

## 故障排查

### 1. 无法访问网站

```bash
# 检查服务状态
docker-compose ps
systemctl status lab-inventory
systemctl status nginx

# 检查端口监听
netstat -tlnp | grep -E '80|443|5000'

# 检查防火墙
ufw status
iptables -L -n
```

### 2. 数据库连接失败

```bash
# 检查 MySQL 状态
systemctl status mysql

# 测试连接
mysql -u lab_user -p -e "USE lab_inventory; SHOW TABLES;"
```

### 3. 502 Bad Gateway

```bash
# 检查后端服务是否运行
curl http://localhost:5000/api/materials

# 检查 Gunicorn 日志
tail -f /opt/lab-inventory/backend/logs/error.log
```

---

## 安全建议

1. **修改默认密码**：部署后立即修改 admin 和 visitor 的默认密码
2. **定期更新**：定期更新系统和依赖包
3. **配置防火墙**：只开放必要的端口（80, 443, 22）
4. **启用 HTTPS**：使用 SSL 证书加密通信
5. **定期备份**：设置自动备份任务
6. **监控告警**：配置服务器监控和告警

---

## 联系支持

部署过程中遇到问题？
- 查看日志：`docker-compose logs` 或 `journalctl -u lab-inventory`
- 检查配置：确保所有配置文件中的密码和密钥已修改
- 网络问题：检查安全组规则和防火墙设置
