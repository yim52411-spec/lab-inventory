#!/usr/bin/env python3
import os
os.environ.setdefault('FLASK_SKIP_DOTENV', '1')
"""兼容旧启动命令，统一复用 run.py 中的应用实例。"""
from run import app
from app import db


def ensure_local_database():
    """本地开发启动时确保数据库表存在；初始账号仍由 init_data.py 创建。"""
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    ensure_local_database()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5001')), debug=app.debug)
