"""
应用启动脚本
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Category, Material, Supplier

app = create_app(os.getenv('FLASK_CONFIG', 'development'))

INITIAL_ADMIN_PASSWORD = os.getenv('INITIAL_ADMIN_PASSWORD')
INITIAL_VISITOR_PASSWORD = os.getenv('INITIAL_VISITOR_PASSWORD')


@app.cli.command()
def init_db():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        print('数据库表创建成功！')
        
        # 检查是否已有管理员
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # 创建默认管理员
            admin = User(
                username='admin',
                name='系统管理员',
                role='admin',
                department='实验室管理部',
                email='admin@lab.com',
                phone='13800138000',
                is_active=True
            )
            if not INITIAL_ADMIN_PASSWORD:
                raise RuntimeError('首次初始化必须设置 INITIAL_ADMIN_PASSWORD')
            admin.set_password(INITIAL_ADMIN_PASSWORD)
            db.session.add(admin)
            
            # 创建默认访问者
            visitor = User(
                username='visitor',
                name='演示用户',
                role='visitor',
                department='实验室',
                email='visitor@lab.com',
                phone='13900139000',
                is_active=True
            )
            visitor.set_password(INITIAL_VISITOR_PASSWORD or INITIAL_ADMIN_PASSWORD)
            db.session.add(visitor)
            
            # 创建默认分类
            categories = [
                Category(name='化学试剂', code='chemical', description='各类化学试剂'),
                Category(name='实验耗材', code='consumable', description='一次性实验耗材'),
                Category(name='仪器设备', code='equipment', description='实验仪器设备'),
                Category(name='玻璃器皿', code='glassware', description='玻璃实验器材')
            ]
            for cat in categories:
                db.session.add(cat)
            
            # 创建示例供应商
            supplier = Supplier(
                name='示例供应商',
                contact_person='张经理',
                phone='010-12345678',
                email='supplier@example.com'
            )
            db.session.add(supplier)
            
            db.session.commit()
            print('默认数据创建成功！')
            print('管理员账号已创建，请使用 INITIAL_ADMIN_PASSWORD 登录')
        else:
            print('数据库已有数据，跳过初始化')


@app.cli.command()
def create_admin():
    """创建管理员账号"""
    import click
    
    username = click.prompt('用户名')
    password = click.prompt('密码', hide_input=True)
    name = click.prompt('姓名')
    
    with app.app_context():
        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f'用户 {username} 已存在！')
            return
        
        admin = User(
            username=username,
            name=name,
            role='admin',
            is_active=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f'管理员 {username} 创建成功！')


@app.cli.command()
def check_alerts():
    """手动检查库存预警"""
    with app.app_context():
        from app.models import Alert
        from sqlalchemy import and_
        
        # 查找库存低于阈值的物料
        materials = Material.query.filter(
            Material.stock <= Material.threshold
        ).all()
        
        new_alerts = []
        for material in materials:
            # 检查是否已存在未解决的预警
            existing = Alert.query.filter(
                and_(
                    Alert.material_id == material.id,
                    Alert.is_resolved == False
                )
            ).first()
            
            if not existing:
                level = 'danger' if material.stock <= 0 else 'warning'
                alert = Alert(
                    material_id=material.id,
                    alert_type='stock_low',
                    level=level,
                    current_stock=material.stock,
                    threshold=material.threshold
                )
                db.session.add(alert)
                new_alerts.append(alert)
        
        db.session.commit()
        print(f'发现 {len(new_alerts)} 条新预警')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=app.debug)
