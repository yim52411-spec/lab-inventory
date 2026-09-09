# Windows 公司局域网部署说明

## 推荐结构

Windows 电脑运行 Docker Desktop，系统通过 Nginx 对外提供 80 端口：

```text
同事浏览器 -> http://服务器IP/ -> Nginx -> Flask 后端
                                      -> MySQL（仅容器内部）
```

同事访问地址：`http://Windows电脑IP/`

## 一、准备 Windows 服务器

1. 安装 Windows 10/11 Pro 或 Windows Server。
2. 将网络设置为“专用网络”。
3. 给电脑设置固定局域网 IP，例如 `192.168.1.50`。
4. 安装并启动 Docker Desktop，选择 Linux containers。
5. 确认 Docker Desktop 已启动：

```powershell
docker --version
docker compose version
```

## 二、复制项目

将本压缩包解压到：

```text
C:\lab-inventory
```

打开 PowerShell：

```powershell
cd C:\lab-inventory
```

## 三、创建环境变量

复制环境变量模板：

```powershell
Copy-Item .\backend\.env.example .\.env
notepad .\.env
```

至少修改以下配置：

```text
MYSQL_ROOT_PASSWORD=设置一个强密码
MYSQL_PASSWORD=设置一个不同的强密码
SECRET_KEY=随机长字符串
JWT_SECRET_KEY=另一组随机长字符串
INITIAL_ADMIN_PASSWORD=首次管理员密码
INITIAL_VISITOR_USERNAME=visitor
INITIAL_VISITOR_PASSWORD=首次访问者密码
CORS_ORIGINS=
```

同源部署时 `CORS_ORIGINS` 可以留空。不要把 `.env` 上传到公开仓库或发给其他人。

## 四、启动服务

首次启动：

```powershell
docker compose up -d --build
docker compose ps
```

等待服务显示为运行状态后，初始化数据库：

```powershell
docker compose exec backend python init_data.py
```

如果数据库已经初始化过，不要重复执行初始化命令。

本机检查：

```powershell
Invoke-WebRequest http://127.0.0.1/api/health
```

应返回包含 `status: ok` 的结果。

## 五、设置 Windows 防火墙

只允许公司局域网访问 80 端口。下面以 `192.168.1.0/24` 为例，请替换成实际网段：

```powershell
New-NetFirewallRule `
  -DisplayName "Lab Inventory LAN HTTP" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 80 `
  -RemoteAddress 192.168.1.0/24 `
  -Profile Private
```

不要对外开放 MySQL 3306 或后端 5000 端口。本项目当前只通过 Nginx 的 80 端口访问。

## 六、同事访问

先在服务器上查看 IP：

```powershell
ipconfig
```

同事在浏览器访问：

```text
http://192.168.1.50/
```

将 `192.168.1.50` 替换成实际 Windows 电脑 IP。

## 七、日常管理

```powershell
cd C:\lab-inventory
docker compose ps
docker compose logs -f backend
docker compose logs -f
docker compose restart
docker compose down
```

## 八、备份

数据库数据保存在 Docker volume 中。定期执行：

```powershell
docker compose exec mysql mysqldump -uroot -p lab_inventory > .\backup_lab_inventory.sql
```

上传文件在 `backend\uploads`，Excel 备份在 `backend\backups`，也需要一并备份。

## 九、重要说明

- 本包不包含真实 `.env` 密钥。
- 本包不自动导入旧 SQLite 数据库；Docker 部署默认使用 MySQL。
- SQLite 文件如需迁移，需要另外设计数据迁移，不建议直接覆盖 MySQL。
- 首次登录后立即修改管理员和访问者密码。
- 局域网访问不需要 ngrok。只有需要公网临时访问时才使用 ngrok，并应增加认证和访问限制。
