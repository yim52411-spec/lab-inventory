#!/bin/bash
# 实验室物料库存管理系统 - 部署脚本
# 用于在阿里云服务器上一键部署

set -e  # 遇到错误立即退出

echo "=========================================="
echo "实验室物料库存管理系统 - 部署脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="/opt/lab-inventory"

# 检查是否以 root 身份运行
if [ "$EUID" -ne 0 ]; then
   echo -e "${RED}请使用 root 权限运行此脚本${NC}"
   exit 1
fi

# 步骤1: 更新系统
echo -e "${YELLOW}[1/8] 更新系统...${NC}"
apt-get update && apt-get upgrade -y

# 步骤2: 安装 Docker
echo -e "${YELLOW}[2/8] 安装 Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl start docker
    systemctl enable docker
    echo -e "${GREEN}Docker 安装完成${NC}"
else
    echo -e "${GREEN}Docker 已安装${NC}"
fi

# 步骤3: 安装 Docker Compose
echo -e "${YELLOW}[3/8] 安装 Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    apt-get install docker-compose -y
    echo -e "${GREEN}Docker Compose 安装完成${NC}"
else
    echo -e "${GREEN}Docker Compose 已安装${NC}"
fi

# 步骤4: 创建项目目录
echo -e "${YELLOW}[4/8] 创建项目目录...${NC}"
mkdir -p $PROJECT_DIR
mkdir -p $PROJECT_DIR/ssl
mkdir -p $PROJECT_DIR/mysql

# 步骤5: 复制项目文件
echo -e "${YELLOW}[5/8] 复制项目文件...${NC}"
echo -e "${YELLOW}请将项目文件复制到 $PROJECT_DIR 目录${NC}"
echo -e "${YELLOW}可以使用: scp -r /本地路径/* root@服务器IP:$PROJECT_DIR/${NC}"

# 检查项目文件是否存在
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo -e "${RED}错误: 未找到 docker-compose.yml 文件${NC}"
    echo -e "${RED}请先上传项目文件到 $PROJECT_DIR 目录${NC}"
    exit 1
fi

# 步骤6: 配置环境变量
echo -e "${YELLOW}[6/8] 配置环境变量...${NC}"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f "$PROJECT_DIR/backend/.env.example" ]; then
        cp $PROJECT_DIR/backend/.env.example $PROJECT_DIR/.env
        echo -e "${YELLOW}请编辑 $PROJECT_DIR/.env 文件，修改数据库密码和密钥${NC}"
        echo -e "${YELLOW}生成随机密钥命令: openssl rand -base64 32${NC}"
    fi
fi

# 步骤7: 启动服务
echo -e "${YELLOW}[7/8] 启动服务...${NC}"
cd $PROJECT_DIR

# 创建必要目录
mkdir -p backend/logs backend/uploads

# 启动服务
docker-compose down 2>/dev/null || true
docker-compose up -d

# 等待服务启动
sleep 10

# 步骤8: 初始化数据库
echo -e "${YELLOW}[8/8] 初始化数据库...${NC}"
docker-compose exec -T backend flask db init 2>/dev/null || true
docker-compose exec -T backend flask db migrate -m "Initial migration" 2>/dev/null || true
docker-compose exec -T backend flask db upgrade 2>/dev/null || true

# 创建初始数据
docker-compose exec -T backend python init_data.py 2>/dev/null || true

echo ""
echo "=========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "=========================================="
echo ""
echo "服务状态:"
docker-compose ps
echo ""
echo "访问地址:"
echo "  - HTTP:  http://$(curl -s ifconfig.me)"
echo "  - HTTPS: https://your-domain.com (配置域名后)"
echo ""
echo "默认账号:"
echo "  - 管理员: admin / admin"
echo "  - 访问者: visitor / visitor"
echo ""
echo "常用命令:"
echo "  - 查看日志: docker-compose logs -f"
echo "  - 重启服务: docker-compose restart"
echo "  - 停止服务: docker-compose down"
echo "  - 进入容器: docker-compose exec backend bash"
echo ""
echo "=========================================="
echo -e "${YELLOW}重要提示:${NC}"
echo -e "${YELLOW}1. 请立即修改默认密码${NC}"
echo -e "${YELLOW}2. 配置域名和 SSL 证书${NC}"
echo -e "${YELLOW}3. 配置邮件服务用于库存预警${NC}"
echo -e "${YELLOW}4. 定期备份数据库${NC}"
echo "=========================================="
