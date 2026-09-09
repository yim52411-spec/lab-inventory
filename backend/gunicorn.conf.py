"""
Gunicorn 配置文件
用于生产环境部署
"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 绑定的地址和端口
bind = "0.0.0.0:5000"

# 当前 JWT 撤销列表保存在进程内存中，必须使用单进程才能保证注销状态一致。
# 内网试用阶段优先保证会话安全；后续接入 Redis 后再提高进程数。
workers = 1

# 工作进程类型 - 使用gevent提高并发性能
worker_class = "gevent"

# 每个工作进程的连接数
worker_connections = 1000

# 超时时间（秒）
timeout = 120

# 保持连接时间（秒）
keepalive = 5

# 日志配置
accesslog = os.path.join(BASE_DIR, "logs", "access.log")
errorlog = os.path.join(BASE_DIR, "logs", "error.log")
loglevel = "info"

# 进程名称
proc_name = "lab_inventory"

# 守护进程模式 - 后台运行
daemon = False

# 进程PID文件
pidfile = os.path.join(BASE_DIR, "logs", "gunicorn.pid")

# 预加载应用 - 节省内存
preload_app = True

# 最大请求数 - 防止内存泄漏
max_requests = 1000
max_requests_jitter = 50


def on_starting(server):
    """启动前创建日志目录"""
    log_dir = os.path.join(BASE_DIR, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)


def on_reload(server):
    """重新加载时"""
    pass
