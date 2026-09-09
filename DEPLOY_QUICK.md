# 快速部署与访问确认

## 1. 上传并解压

把 `lab-inventory-cloud-package.zip` 上传到云服务器，例如 `/opt`：

```bash
cd /opt
unzip lab-inventory-cloud-package.zip
cd lab-inventory
```

## 2. 修改必要配置

编辑 `docker-compose.yml`，至少修改这些值：

- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `DATABASE_URL` 里的数据库密码
- `SECRET_KEY`
- `JWT_SECRET_KEY`

可以用下面命令生成随机密钥：

```bash
openssl rand -base64 32
```

如果云服务器用安全组或防火墙，确认已开放 `80` 端口。

## 3. 启动

服务器已安装 Docker 和 Docker Compose 插件时：

```bash
docker compose up -d --build
docker compose ps
```

如果服务器只支持旧命令：

```bash
docker-compose up -d --build
docker-compose ps
```

初始化数据库：

```bash
docker compose exec backend python init_data.py
```

旧命令环境把 `docker compose` 改成 `docker-compose`。

## 4. 确认访问链接

查看公网 IP：

```bash
curl -s ifconfig.me
```

访问链接就是：

```text
http://你的公网IP/
```

也可以在服务器上检查接口是否正常：

```bash
curl http://127.0.0.1/api/health
```

返回包含 `status: ok` 或浏览器能打开登录页，就说明链接可访问。

默认账号：

- 管理员：`admin / admin`
- 访问者：`visitor / visitor`

上线后请立即修改默认密码。
