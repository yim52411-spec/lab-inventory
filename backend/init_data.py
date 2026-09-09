"""
初始化数据库数据脚本
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Category, Material, Supplier, SystemSetting

app = create_app(os.getenv('FLASK_CONFIG', 'development'))

INITIAL_ADMIN_PASSWORD = os.getenv('INITIAL_ADMIN_PASSWORD')
INITIAL_VISITOR_USERNAME = os.getenv('INITIAL_VISITOR_USERNAME')
INITIAL_VISITOR_PASSWORD = os.getenv('INITIAL_VISITOR_PASSWORD')

with app.app_context():
    db.create_all()

    # 检查是否已有管理员
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print('创建默认数据...')
        
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
        visitor_password = INITIAL_VISITOR_PASSWORD or INITIAL_ADMIN_PASSWORD
        visitor.set_password(visitor_password)
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
        
        db.session.flush()  # 获取分类ID
        
        # 创建示例供应商
        supplier = Supplier(
            name='示例供应商',
            contact_person='张经理',
            phone='010-12345678',
            email='supplier@example.com'
        )
        db.session.add(supplier)
        db.session.flush()
        
        # 创建示例物料
        materials = [
            Material(
                code='M2024001',
                name='乙醇 (分析纯)',
                category_id=1,
                spec='500ml/瓶',
                unit='瓶',
                stock=2,
                threshold=10,
                location='A区-01架',
                supplier_id=1,
                status='danger'
            ),
            Material(
                code='M2024002',
                name='离心管 15ml',
                category_id=2,
                spec='50个/包',
                unit='个',
                stock=15,
                threshold=20,
                location='B区-03架',
                supplier_id=1,
                status='warning'
            ),
            Material(
                code='M2024003',
                name='培养皿',
                category_id=4,
                spec='90mm',
                unit='个',
                stock=20,
                threshold=30,
                location='C区-02架',
                supplier_id=1,
                status='warning'
            ),
            Material(
                code='M2024004',
                name='电子天平',
                category_id=3,
                spec='0.1mg精度',
                unit='台',
                stock=5,
                threshold=2,
                location='D区-仪器室',
                supplier_id=1,
                status='normal'
            ),
            Material(
                code='M2024005',
                name='移液器',
                category_id=3,
                spec='100-1000μl',
                unit='支',
                stock=8,
                threshold=3,
                location='D区-仪器室',
                supplier_id=1,
                status='normal'
            )
        ]
        for mat in materials:
            db.session.add(mat)
        
        db.session.commit()
        print('✅ 默认数据创建成功！')
        print('')
        print('管理员账号已创建，请使用 INITIAL_ADMIN_PASSWORD 登录')
        print('')
    else:
        print('数据库已有数据，跳过初始化')

    if INITIAL_VISITOR_USERNAME and INITIAL_VISITOR_PASSWORD and not User.query.filter_by(username=INITIAL_VISITOR_USERNAME).first():
        visitor = User(
            username=INITIAL_VISITOR_USERNAME,
            name=INITIAL_VISITOR_USERNAME,
            role='visitor',
            department='实验室',
            email='',
            phone='',
            is_active=True
        )
        visitor.set_password(INITIAL_VISITOR_PASSWORD)
        db.session.add(visitor)
        db.session.commit()
        print(f'访问者账号已创建: {INITIAL_VISITOR_USERNAME}')

    default_settings = {
        'alert_email': ('admin@lab.com', '库存预警邮件接收地址'),
        'alert_check_interval': ('30', '预警检查频率，单位分钟'),
        'alert_email_enabled': ('true', '库存不足或预警时发送邮件'),
        'overdue_email_enabled': ('false', '借用逾期时发送邮件'),
        'storage_location': ('cloud', '数据存储位置'),
        'backup_frequency': ('daily', '自动备份频率')
    }
    for key, (value, description) in default_settings.items():
        if not SystemSetting.query.filter_by(key=key).first():
            db.session.add(SystemSetting(key=key, value=value, description=description))
    db.session.commit()
