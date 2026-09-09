"""
配置文件
"""
import os
from datetime import timedelta

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """基础配置"""
    
    # 密钥配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'local-development-secret-key'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'local-development-jwt-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # 数据库配置
    # 默认使用SQLite，生产环境可切换到MySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(BASE_DIR, "lab_inventory.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 邮件配置 - 用于库存预警通知
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # 预警配置
    ALERT_CHECK_INTERVAL = 30  # 预警检查间隔（分钟）
    ALERT_EMAIL_ENABLED = True  # 是否启用邮件预警
    
    # 分页配置
    ITEMS_PER_PAGE = 20
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    # CORS配置
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            'CORS_ORIGINS',
            'http://localhost,http://localhost:80,http://localhost:8080,'
            'http://127.0.0.1,http://127.0.0.1:8080,'
            ''
        ).split(',')
        if origin.strip()
    ]


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    
    # 生产环境必须显式设置密钥，禁止使用默认值。
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')



class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
