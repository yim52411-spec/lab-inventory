#!/bin/bash
# 实验室物料库存管理系统 - 服务器自动部署脚本
# 在阿里云服务器上执行此脚本

set -e

echo "=========================================="
echo "实验室物料库存管理系统 - 服务器部署"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/opt/lab-inventory"

# 检查是否以 root 身份运行
if [ "$EUID" -ne 0 ]; then
   echo -e "${RED}请使用 root 权限运行此脚本${NC}"
   exit 1
fi

# 步骤1: 更新系统
echo -e "${YELLOW}[1/10] 更新系统...${NC}"
apt-get update -y
apt-get upgrade -y

# 步骤2: 安装必要工具
echo -e "${YELLOW}[2/10] 安装必要工具...${NC}"
apt-get install -y curl wget git vim net-tools

# 步骤3: 安装 Docker
echo -e "${YELLOW}[3/10] 安装 Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl start docker
    systemctl enable docker
    usermod -aG docker root
    echo -e "${GREEN}Docker 安装完成${NC}"
else
    echo -e "${GREEN}Docker 已安装，版本: $(docker --version)${NC}"
fi

# 步骤4: 安装 Docker Compose
echo -e "${YELLOW}[4/10] 安装 Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    apt-get install -y docker-compose
    echo -e "${GREEN}Docker Compose 安装完成${NC}"
else
    echo -e "${GREEN}Docker Compose 已安装，版本: $(docker-compose --version)${NC}"
fi

# 步骤5: 创建项目目录
echo -e "${YELLOW}[5/10] 创建项目目录...${NC}"
mkdir -p $PROJECT_DIR
mkdir -p $PROJECT_DIR/ssl
mkdir -p $PROJECT_DIR/mysql
mkdir -p $PROJECT_DIR/backend/logs
mkdir -p $PROJECT_DIR/backend/uploads
cd $PROJECT_DIR

# 步骤6: 等待用户上传文件
echo -e "${YELLOW}[6/10] 准备项目文件...${NC}"
echo -e "${YELLOW}请确保已将项目文件上传到 $PROJECT_DIR 目录${NC}"

# 检查必要文件
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo -e "${RED}错误: 未找到 docker-compose.yml 文件${NC}"
    echo -e "${YELLOW}请先在本地执行以下命令上传文件:${NC}"
    echo -e "${GREEN}scp -r /path/to/lab-inventory/* root@8.166.118.116:$PROJECT_DIR/${NC}"
    exit 1
fi

echo -e "${GREEN}项目文件检查通过${NC}"

# 步骤7: 生成环境变量
echo -e "${YELLOW}[7/10] 生成环境变量...${NC}"

# 生成随机密钥
SECRET_KEY=$(openssl rand -base64 32)
JWT_SECRET_KEY=$(openssl rand -base64 32)
MYSQL_ROOT_PASSWORD=$(openssl rand -base64 16)
MYSQL_PASSWORD=$(openssl rand -base64 16)

# 创建 .env 文件
cat > $PROJECT_DIR/.env << EOF
# Flask 配置
FLASK_APP=run.py
FLASK_CONFIG=production

# 密钥配置
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET_KEY

# 数据库配置
DATABASE_URL=mysql+pymysql://lab_user:$MYSQL_PASSWORD@mysql:3306/lab_inventory?charset=utf8mb4

# MySQL 配置
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_DATABASE=lab_inventory
MYSQL_USER=lab_user
MYSQL_PASSWORD=$MYSQL_PASSWORD

# 邮件配置（请根据实际情况修改）
MAIL_SERVER=smtp.company.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your_email@company.com
MAIL_PASSWORD=your_email_password
MAIL_DEFAULT_SENDER=your_email@company.com
EOF

echo -e "${GREEN}环境变量已生成并保存到 $PROJECT_DIR/.env${NC}"
echo -e "${YELLOW}请编辑 .env 文件，修改邮件配置${NC}"

# 步骤8: 启动服务
echo -e "${YELLOW}[8/10] 启动 Docker 服务...${NC}"
cd $PROJECT_DIR

# 停止已有服务
docker-compose down 2>/dev/null || true

# 启动服务
docker-compose up -d

# 等待服务启动
echo -e "${YELLOW}等待服务启动...${NC}"
sleep 30

# 步骤9: 初始化数据库
echo -e "${YELLOW}[9/10] 初始化数据库...${NC}"

# 等待 MySQL 就绪
echo -e "${YELLOW}等待 MySQL 就绪...${NC}"
until docker-compose exec -T mysql mysql -uroot -p$MYSQL_ROOT_PASSWORD -e "SELECT 1" > /dev/null 2>&1; do
    echo -e "${YELLOW}等待 MySQL...${NC}"
    sleep 5
done

echo -e "${GREEN}MySQL 已就绪${NC}"

# 初始化数据库
docker-compose exec -T backend flask db init 2>/dev/null || true
sleep 2
docker-compose exec -T backend flask db migrate -m "Initial migration" 2>/dev/null || true
sleep 2
docker-compose exec -T backend flask db upgrade 2>/dev/null || true
sleep 2

# 创建初始数据
docker-compose exec -T backend python init_data.py 2>/dev/null || true

echo -e "${GREEN}数据库初始化完成${NC}"

# 步骤10: 配置防火墙
echo -e "${YELLOW}[10/10] 配置防火墙...${NC}"

# 检查并安装 ufw
if ! command -v ufw &> /dev/null; then
    apt-get install -y ufw
fi

# 配置防火墙
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo -e "${GREEN}防火墙配置完成${NC}"

# 显示部署信息
echo ""
echo "=========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  - HTTP:  http://8.166.118.116"
echo ""
echo "默认账号:"
echo "  - 管理员: admin / admin"
echo "  - 访问者: visitor / visitor"
echo ""
echo "重要文件:"
echo "  - 环境变量: $PROJECT_DIR/.env"
echo "  - 日志目录: $PROJECT_DIR/backend/logs/"
echo "  - 上传目录: $PROJECT_DIR/backend/uploads/"
echo ""
echo "常用命令:"
echo "  cd $PROJECT_DIR"
echo "  docker-compose ps          # 查看服务状态"
echo "  docker-compose logs -f     # 查看日志"
echo "  docker-compose restart     # 重启服务"
echo "  docker-compose down        # 停止服务"
echo ""
echo "=========================================="
echo -e "${YELLOW}重要提示:${NC}"
echo -e "${YELLOW}1. 请立即修改默认密码${NC}"
echo -e "${YELLOW}2. 编辑 $PROJECT_DIR/.env 配置邮件服务${NC}"
echo -e "${YELLOW}3. 建议注册域名并配置 HTTPS${NC}"
echo -e "${YELLOW}4. 定期备份数据库${NC}"
echo "=========================================="
