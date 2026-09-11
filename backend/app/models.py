"""
数据库模型定义
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='visitor')  # admin, visitor
    department = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    purchase_requests = db.relationship('PurchaseRequest', foreign_keys='PurchaseRequest.user_id', backref='requester', lazy='dynamic')
    borrow_records = db.relationship('BorrowRecord', backref='borrower', lazy='dynamic')
    operation_records = db.relationship('OperationRecord', backref='operator', lazy='dynamic')
    
    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """检查是否为管理员"""
        return self.role == 'admin'
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'role': self.role,
            'department': self.department,
            'email': self.email,
            'phone': self.phone,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class Category(db.Model):
    """物料分类模型"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    materials = db.relationship('Material', backref='category', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description
        }


class Supplier(db.Model):
    """供应商模型"""
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    remark = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    materials = db.relationship('Material', backref='supplier', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'contact_person': self.contact_person,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'remark': self.remark,
            'is_active': self.is_active
        }


class Material(db.Model):
    """物料模型"""
    __tablename__ = 'materials'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    spec = db.Column(db.String(100))  # 规格型号
    unit = db.Column(db.String(20), default='个')  # 单位
    stock = db.Column(db.Integer, default=0)  # 当前库存
    threshold = db.Column(db.Integer, default=10)  # 预警阈值
    location = db.Column(db.String(100))  # 存放位置
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    remark = db.Column(db.Text)
    status = db.Column(db.String(20), default='normal')  # normal, warning, danger
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    purchase_requests = db.relationship('PurchaseRequest', backref='material', lazy='dynamic')
    borrow_records = db.relationship('BorrowRecord', backref='material', lazy='dynamic')
    operation_records = db.relationship('OperationRecord', backref='material', lazy='dynamic')
    alerts = db.relationship('Alert', backref='material', lazy='dynamic')
    batches = db.relationship('MaterialBatch', backref='material', lazy='dynamic', cascade='all, delete-orphan')
    
    def update_status(self):
        """根据库存更新状态"""
        if self.stock <= 0:
            self.status = 'danger'
        elif self.stock <= self.threshold:
            self.status = 'warning'
        else:
            self.status = 'normal'
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'spec': self.spec,
            'unit': self.unit,
            'stock': self.stock,
            'threshold': self.threshold,
            'location': self.location,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else None,
            'remark': self.remark,
            'status': self.status,
            'batches': [batch.to_dict() for batch in self.batches.order_by(MaterialBatch.received_at.asc()).all()],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class MaterialBatch(db.Model):
    """同一物料的独立采购入库批次，支持先进先出和批次级到期预警。"""
    __tablename__ = 'material_batches'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=False, index=True)
    batch_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    production_date = db.Column(db.Date)
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expiry_date = db.Column(db.Date)
    shelf_life_days = db.Column(db.Integer)
    quantity_received = db.Column(db.Integer, nullable=False)
    quantity_remaining = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'material_id': self.material_id,
            'batch_no': self.batch_no,
            'production_date': self.production_date.isoformat() if self.production_date else None,
            'received_at': self.received_at.strftime('%Y-%m-%d %H:%M:%S') if self.received_at else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'shelf_life_days': self.shelf_life_days,
            'quantity_received': self.quantity_received,
            'quantity_remaining': self.quantity_remaining,
        }


class PurchaseRequest(db.Model):
    """采购申请模型"""
    __tablename__ = 'purchase_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(20), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'))
    material_name = db.Column(db.String(100), nullable=False)  # 物料名称（新物料可能没有ID）
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    spec = db.Column(db.String(100))  # 规格
    quantity = db.Column(db.Integer, nullable=False)
    supplier_link = db.Column(db.String(500))  # 供应商链接
    estimated_price = db.Column(db.Numeric(10, 2))  # 预计单价
    reason = db.Column(db.Text, nullable=False)  # 申请理由
    remark = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    approval_remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    approver = db.relationship('User', foreign_keys=[approver_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'request_no': self.request_no,
            'user_id': self.user_id,
            'requester_name': self.requester.name if self.requester else None,
            'material_id': self.material_id,
            'material_name': self.material_name,
            'category_id': self.category_id,
            'spec': self.spec,
            'quantity': self.quantity,
            'supplier_link': self.supplier_link,
            'estimated_price': float(self.estimated_price) if self.estimated_price else None,
            'reason': self.reason,
            'remark': self.remark,
            'status': self.status,
            'approver_id': self.approver_id,
            'approver_name': self.approver.name if self.approver else None,
            'approved_at': self.approved_at.strftime('%Y-%m-%d %H:%M:%S') if self.approved_at else None,
            'approval_remark': self.approval_remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class BorrowRecord(db.Model):
    """借用记录模型"""
    __tablename__ = 'borrow_records'
    
    id = db.Column(db.Integer, primary_key=True)
    borrow_no = db.Column(db.String(20), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    reason = db.Column(db.Text)
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_return_date = db.Column(db.DateTime, nullable=False)
    actual_return_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')  # active, returned, overdue
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        requires_return = not (
            self.expected_return_date and self.expected_return_date.year >= 2099
        )
        return {
            'id': self.id,
            'borrow_no': self.borrow_no,
            'user_id': self.user_id,
            'borrower_name': self.borrower.name if self.borrower else None,
            'material_id': self.material_id,
            'material_name': self.material.name if self.material else None,
            'quantity': self.quantity,
            'reason': self.reason,
            'borrow_date': self.borrow_date.strftime('%Y-%m-%d %H:%M:%S') if self.borrow_date else None,
            'requires_return': requires_return,
            'expected_return_date': self.expected_return_date.strftime('%Y-%m-%d') if self.expected_return_date and requires_return else '无需归还',
            'actual_return_date': self.actual_return_date.strftime('%Y-%m-%d %H:%M:%S') if self.actual_return_date else None,
            'status': self.status,
            'remark': self.remark
        }


class OperationRecord(db.Model):
    """操作记录模型（出入库记录）"""
    __tablename__ = 'operation_records'
    
    id = db.Column(db.Integer, primary_key=True)
    operation_no = db.Column(db.String(20), unique=True, nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)  # in, out, borrow, return
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'))
    material_name = db.Column(db.String(100))  # 物料名称（冗余存储）
    quantity = db.Column(db.Integer, nullable=False)
    stock_before = db.Column(db.Integer)  # 操作前库存
    stock_after = db.Column(db.Integer)  # 操作后库存
    related_id = db.Column(db.Integer)  # 关联记录ID（如采购申请ID、借用记录ID）
    related_type = db.Column(db.String(20))  # 关联类型
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'operation_no': self.operation_no,
            'type': self.type,
            'type_name': self.get_type_name(),
            'user_id': self.user_id,
            'operator_name': self.operator.name if self.operator else None,
            'material_id': self.material_id,
            'material_name': self.material_name or (self.material.name if self.material else None),
            'quantity': self.quantity,
            'stock_before': self.stock_before,
            'stock_after': self.stock_after,
            'related_id': self.related_id,
            'related_type': self.related_type,
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
    
    def get_type_name(self):
        """获取操作类型名称"""
        type_names = {
            'in': '入库',
            'out': '出库',
            'borrow': '借用',
            'return': '归还',
            'purchase': '采购入库',
            'adjust': '库存调整',
            'scrap': '过期报废'
        }
        return type_names.get(self.type, self.type)


class Alert(db.Model):
    """库存预警记录模型"""
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('material_batches.id'), nullable=True, index=True)
    alert_type = db.Column(db.String(20), default='stock_low')  # stock_low, expiry
    level = db.Column(db.String(20), default='warning')  # warning, danger
    current_stock = db.Column(db.Integer)
    threshold = db.Column(db.Integer)
    is_sent = db.Column(db.Boolean, default=False)  # 是否已发送邮件通知
    sent_at = db.Column(db.DateTime)
    is_resolved = db.Column(db.Boolean, default=False)  # 是否已解决
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    batch = db.relationship('MaterialBatch', backref='alerts')
    
    def to_dict(self):
        return {
            'id': self.id,
            'material_id': self.material_id,
            'material_name': self.material.name if self.material else None,
            'material_code': self.material.code if self.material else None,
            'batch_id': self.batch_id,
            'batch_no': self.batch.batch_no if self.batch else None,
            'production_date': self.batch.production_date.isoformat() if self.batch and self.batch.production_date else None,
            'expiry_date': self.batch.expiry_date.isoformat() if self.batch and self.batch.expiry_date else None,
            'alert_type': self.alert_type,
            'level': self.level,
            'current_stock': self.current_stock,
            'threshold': self.threshold,
            'is_sent': self.is_sent,
            'sent_at': self.sent_at.strftime('%Y-%m-%d %H:%M:%S') if self.sent_at else None,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if self.resolved_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class SystemSetting(db.Model):
    """系统设置键值表"""
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
