#!/bin/bash
# 系统诊断脚本
# 在服务器上执行此脚本检查问题

echo "=========================================="
echo "系统诊断报告"
echo "=========================================="
echo ""

echo "【1】检查Docker服务状态"
echo "----------------------------------------"
systemctl status docker --no-pager | head -20
echo ""

echo "【2】检查运行中的容器"
echo "----------------------------------------"
docker ps
echo ""

echo "【3】检查所有容器（包括停止的）"
echo "----------------------------------------"
docker ps -a
echo ""

echo "【4】检查端口监听情况"
echo "----------------------------------------"
netstat -tlnp | grep -E '80|443|5000|3306'
echo ""

echo "【5】检查防火墙状态"
echo "----------------------------------------"
ufw status
echo ""

echo "【6】检查Nginx服务"
echo "----------------------------------------"
docker logs lab_inventory_nginx 2>&1 | tail -20
echo ""

echo "【7】检查后端服务日志"
echo "----------------------------------------"
docker logs lab_inventory_backend 2>&1 | tail -30
echo ""

echo "【8】检查MySQL服务"
echo "----------------------------------------"
docker logs lab_inventory_mysql 2>&1 | tail -20
echo ""

echo "【9】检查项目目录"
echo "----------------------------------------"
ls -la /opt/lab-inventory/
echo ""

echo "【10】检查docker-compose配置"
echo "----------------------------------------"
cd /opt/lab-inventory && docker-compose config | head -50
echo ""

echo "=========================================="
echo "诊断完成"
echo "=========================================="
