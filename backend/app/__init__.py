"""
应用工厂模式
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_mail import Mail
from config import config

# 初始化扩展（不绑定应用）
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
mail = Mail()


def create_app(config_name='default'):
    """应用工厂函数"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    if config_name == 'production' and (
        not app.config.get('SECRET_KEY') or not app.config.get('JWT_SECRET_KEY')
    ):
        raise RuntimeError('生产环境必须设置 SECRET_KEY 和 JWT_SECRET_KEY')
    
    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from app.api.auth import revoked_tokens
        return jwt_payload.get('jti') in revoked_tokens

    mail.init_app(app)
    
    # 启用CORS，允许前端访问
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', []),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    
    # 注册蓝图
    from app.api.auth import auth_bp, login
    from app.api.materials import materials_bp
    from app.api.inventory import inventory_bp
    from app.api.purchase import purchase_bp
    from app.api.borrow import borrow_bp
    from app.api.alerts import alerts_bp
    from app.api.users import users_bp
    from app.api.records import records_bp
    from app.api.settings import settings_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(materials_bp, url_prefix='/api/materials')
    app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
    app.register_blueprint(purchase_bp, url_prefix='/api/purchase')
    app.register_blueprint(borrow_bp, url_prefix='/api/borrow')
    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(records_bp, url_prefix='/api/records')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.add_url_rule('/api/login', endpoint='legacy_login', view_func=login, methods=['POST'])
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return {'success': True, 'status': 'ok'}, 200
    
    # 注册错误处理
    register_error_handlers(app)
    
    # 创建上传目录
    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 后台每分钟检查一次，具体频率由系统设置中的 alert_check_interval 决定。
    # Flask debug reloader 会创建父子两个进程；只让实际服务进程启动调度器，避免重复检查/发信。
    scheduler_process = not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    if not app.testing and scheduler_process:
        from flask_apscheduler import APScheduler
        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.add_job(
            id='alert-and-backup-check',
            func='app.api.scheduler:run_scheduled_tasks',
            args=[app],
            trigger='interval',
            minutes=1,
            replace_existing=True,
        )
        scheduler.start()
        app.extensions['scheduler'] = scheduler
    
    return app


def register_error_handlers(app):
    """注册错误处理器"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return {'success': False, 'message': '请求参数错误'}, 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return {'success': False, 'message': '未授权访问'}, 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return {'success': False, 'message': '禁止访问'}, 403
    
    @app.errorhandler(404)
    def not_found(error):
        return {'success': False, 'message': '资源不存在'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'success': False, 'message': '服务器内部错误'}, 500
