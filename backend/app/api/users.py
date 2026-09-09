"""
用户管理API
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import or_
from app import db
from app.models import User
from app.api.auth import admin_required, get_current_user_id

users_bp = Blueprint('users', __name__)


@users_bp.route('', methods=['GET'])
@admin_required
def get_users():
    """获取用户列表（管理员）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '')
    role = request.args.get('role', '')
    
    query = User.query
    
    if keyword:
        query = query.filter(
            or_(
                User.username.contains(keyword),
                User.name.contains(keyword),
                User.department.contains(keyword)
            )
        )
    
    if role:
        query = query.filter(User.role == role)
    
    query = query.order_by(User.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'data': {
            'items': [u.to_dict() for u in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }
    })


@users_bp.route('/<int:id>', methods=['GET'])
@admin_required
def get_user(id):
    """获取用户详情（管理员）"""
    user = User.query.get_or_404(id)
    return jsonify({
        'success': True,
        'data': user.to_dict()
    })


@users_bp.route('', methods=['POST'])
@admin_required
def create_user():
    """创建用户（管理员）"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    # 必填字段验证
    required_fields = ['username', 'password', 'name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field}不能为空'}), 400
    
    # 检查用户名是否已存在
    existing = User.query.filter_by(username=data['username']).first()
    if existing:
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    
    # 创建用户
    user = User(
        username=data['username'],
        name=data['name'],
        role=data.get('role', 'visitor'),
        department=data.get('department', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        is_active=data.get('is_active', True)
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '用户创建成功',
        'data': user.to_dict()
    }), 201


@users_bp.route('/<int:id>', methods=['PUT'])
@admin_required
def update_user(id):
    """更新用户信息（管理员）"""
    user = User.query.get_or_404(id)
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    # 更新字段
    if 'name' in data:
        user.name = data['name']
    if 'role' in data:
        user.role = data['role']
    if 'department' in data:
        user.department = data['department']
    if 'email' in data:
        user.email = data['email']
    if 'phone' in data:
        user.phone = data['phone']
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '用户信息更新成功',
        'data': user.to_dict()
    })


@users_bp.route('/<int:id>/reset-password', methods=['POST'])
@admin_required
def reset_password(id):
    """重置用户密码（管理员）"""
    user = User.query.get_or_404(id)
    data = request.get_json()
    
    new_password = data.get('password', '123456')  # 默认密码
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '密码重置成功',
        'data': {
            'user_id': user.id,
            'new_password': new_password  # 仅在开发环境返回
        }
    })


@users_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    """删除用户（管理员）"""
    user = User.query.get_or_404(id)
    
    # 不能删除自己
    if user.id == get_current_user_id():
        return jsonify({'success': False, 'message': '不能删除当前登录用户'}), 400
    
    # 检查是否有相关记录
    if user.purchase_requests.count() > 0 or user.borrow_records.count() > 0:
        # 软删除：禁用用户
        user.is_active = False
        db.session.commit()
        return jsonify({
            'success': True,
            'message': '用户已禁用（存在关联记录）'
        })
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '用户删除成功'
    })


@users_bp.route('/stats', methods=['GET'])
@admin_required
def get_user_stats():
    """获取用户统计（管理员）"""
    from sqlalchemy import func
    
    total = User.query.count()
    admin_count = User.query.filter_by(role='admin').count()
    visitor_count = User.query.filter_by(role='visitor').count()
    active_count = User.query.filter_by(is_active=True).count()
    
    # 按部门统计
    dept_stats = db.session.query(
        User.department,
        func.count(User.id)
    ).group_by(User.department).all()
    
    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'admin_count': admin_count,
            'visitor_count': visitor_count,
            'active_count': active_count,
            'inactive_count': total - active_count,
            'department_stats': [
                {'department': dept or '未分配', 'count': count}
                for dept, count in dept_stats
            ]
        }
    })
