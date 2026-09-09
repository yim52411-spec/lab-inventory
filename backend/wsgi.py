"""
WSGI 入口文件
用于 Gunicorn 启动应用
"""
import os

os.environ.setdefault('FLASK_CONFIG', 'production')

from run import app

# 如果是直接运行此文件
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
