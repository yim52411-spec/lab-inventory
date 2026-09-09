#!/usr/bin/env python3
import os
"""兼容旧启动命令，统一复用 run.py 中的应用实例。"""
from run import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=app.debug)
