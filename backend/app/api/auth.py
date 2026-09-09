"""
认证相关API
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

# 用于存储已撤销的token（生产环境应使用Redis）
revoked_tokens = set()


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
    
    # 查找用户
    user = User.query.filter_by(username=username, is_active=True).first()
    
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    
    # 创建JWT token - identity必须是字符串
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'username': user.username,
            'role': user.role,
            'name': user.name
        }
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    
    return jsonify({
        'success': True,
        'message': '登录成功',
        'data': {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }
    })


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """刷新访问令牌"""
    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)
    
    if not user or not user.is_active:
        return jsonify({'success': False, 'message': '用户不存在或已被禁用'}), 401
    
    new_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'username': user.username,
            'role': user.role,
            'name': user.name
        }
    )
    
    return jsonify({
        'success': True,
        'data': {
            'access_token': new_token
        }
    })


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """用户退出"""
    jti = get_jwt()['jti']
    revoked_tokens.add(jti)
    return jsonify({'success': True, 'message': '退出成功'})


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """获取当前用户信息"""
    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': user.to_dict()
    })


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """修改密码"""
    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({'success': False, 'message': '旧密码和新密码不能为空'}), 400
    
    if not user.check_password(old_password):
        return jsonify({'success': False, 'message': '旧密码错误'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '新密码长度至少6位'}), 400
    
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '密码修改成功'})


# JWT token撤销检查
# 使用简单的方式，在jwt_required装饰器中处理


def admin_required(fn):
    """管理员权限装饰器"""
    from functools import wraps
    
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return fn(*args, **kwargs)
    
    return wrapper


def get_current_user_id():
    """返回当前令牌中的用户 ID。"""
    return int(get_jwt_identity())
