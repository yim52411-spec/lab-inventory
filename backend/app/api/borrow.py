"""
借用管理API
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from datetime import datetime, timedelta
from app import db
from app.models import BorrowRecord, Material, OperationRecord
from app.api.auth import admin_required, get_current_user_id
from app.api.alerts import sync_material_alert
from app.utils.helpers import generate_code

borrow_bp = Blueprint('borrow', __name__)


@borrow_bp.route('', methods=['GET'])
@jwt_required()
def get_borrow_records():
    """获取借用记录列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    my_records = request.args.get('my', 'false').lower() == 'true'
    role = get_jwt().get('role')
    
    query = BorrowRecord.query
    
    # 访问者只能查看自己的借用记录；管理员可查看全部或按my=true查看自己
    if role != 'admin' or my_records:
        query = query.filter(BorrowRecord.user_id == get_current_user_id())
    
    if status:
        query = query.filter(BorrowRecord.status == status)
    
    query = query.order_by(BorrowRecord.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'data': {
            'items': [r.to_dict() for r in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }
    })


@borrow_bp.route('/summary', methods=['GET'])
@admin_required
def get_borrow_summary():
    """获取管理员借用审批提醒统计"""
    pending = BorrowRecord.query.filter_by(status='pending').count()
    active = BorrowRecord.query.filter_by(status='active').count()
    latest = BorrowRecord.query.filter(
        BorrowRecord.status.in_(['pending'])
    ).order_by(BorrowRecord.created_at.desc()).limit(5).all()

    return jsonify({
        'success': True,
        'data': {
            'pending': pending,
            'active': active,
            'total_attention': pending,
            'latest': [item.to_dict() for item in latest]
        }
    })


@borrow_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_borrow_record(id):
    """获取借用记录详情"""
    record = BorrowRecord.query.get_or_404(id)
    if get_jwt().get('role') != 'admin' and record.user_id != get_current_user_id():
        return jsonify({'success': False, 'message': '无权访问'}), 403
    return jsonify({
        'success': True,
        'data': record.to_dict()
    })


@borrow_bp.route('', methods=['POST'])
@jwt_required()
def create_borrow_request():
    """创建借用申请"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    material_id = data.get('material_id')
    quantity = int(data.get('quantity', 1) or 1)
    requires_return = data.get('requires_return', True)
    if isinstance(requires_return, str):
        requires_return = requires_return.lower() not in ['false', '0', 'no', '不需要归还']
    expected_return_date = data.get('expected_return_date')
    reason = data.get('reason', '')
    
    if not material_id:
        return jsonify({'success': False, 'message': '物料ID不能为空'}), 400
    
    if requires_return and not expected_return_date:
        return jsonify({'success': False, 'message': '预计归还日期不能为空'}), 400
    
    material = Material.query.get(material_id)
    if not material:
        return jsonify({'success': False, 'message': '物料不存在'}), 404
    
    if quantity <= 0:
        return jsonify({'success': False, 'message': '借用数量必须大于0'}), 400

    if requires_return:
        return_date = datetime.strptime(expected_return_date, '%Y-%m-%d')
    else:
        return_date = datetime(2099, 12, 31)
    
    # 创建借用记录
    borrow = BorrowRecord(
        borrow_no=generate_code('B'),
        user_id=get_current_user_id(),
        material_id=material_id,
        quantity=quantity,
        reason=reason,
        expected_return_date=return_date,
        status='pending'
    )

    db.session.add(borrow)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '借用申请已提交，等待管理员审批',
        'data': borrow.to_dict()
    }), 201


@borrow_bp.route('/<int:id>/approve', methods=['POST', 'PUT'])
@admin_required
def approve_borrow(id):
    """审批借用申请（管理员）"""
    borrow = BorrowRecord.query.get_or_404(id)

    if borrow.status != 'pending':
        return jsonify({'success': False, 'message': '该借用申请已处理'}), 400

    data = request.get_json() or {}
    action = data.get('action')
    if action not in ['approve', 'reject']:
        return jsonify({'success': False, 'message': '操作类型错误'}), 400

    if action == 'reject':
        borrow.status = 'rejected'
        db.session.commit()
        return jsonify({'success': True, 'message': '借用申请已拒绝', 'data': borrow.to_dict()})

    material = Material.query.get(borrow.material_id)
    if not material:
        return jsonify({'success': False, 'message': '物料不存在'}), 404

    if material.stock < borrow.quantity:
        return jsonify({
            'success': False,
            'message': f'库存不足，当前库存: {material.stock}'
        }), 400

    stock_before = material.stock
    material.stock -= borrow.quantity
    material.update_status()
    sync_material_alert(material)
    borrow.status = 'active'

    record = OperationRecord(
        operation_no=generate_code('O'),
        type='borrow',
        user_id=get_current_user_id(),
        material_id=material.id,
        material_name=material.name,
        quantity=-borrow.quantity,
        stock_before=stock_before,
        stock_after=material.stock,
        related_id=borrow.id,
        related_type='borrow',
        remark=f'审批借用出库: {borrow.borrow_no}. {borrow.reason or ""}'
    )

    db.session.add(record)
    db.session.commit()

    return jsonify({'success': True, 'message': '借用申请已批准并出库', 'data': borrow.to_dict()})


@borrow_bp.route('/<int:id>/return', methods=['POST', 'PUT'])
@admin_required
def return_borrow(id):
    """归还借用（管理员）"""
    borrow = BorrowRecord.query.get_or_404(id)
    
    if borrow.status != 'active':
        return jsonify({'success': False, 'message': '该借用记录已归还或已逾期'}), 400
    
    data = request.get_json()
    actual_quantity = data.get('actual_quantity', borrow.quantity)
    remark = data.get('remark', '')
    
    material = Material.query.get(borrow.material_id)
    
    # 更新借用记录
    borrow.status = 'returned'
    borrow.actual_return_date = datetime.utcnow()
    
    if material:
        # 更新库存
        stock_before = material.stock
        material.stock += actual_quantity
        material.update_status()
        sync_material_alert(material)
        
        # 创建归还入库记录
        record = OperationRecord(
            operation_no=generate_code('I'),
            type='return',
            user_id=get_current_user_id(),
            material_id=material.id,
            material_name=material.name,
            quantity=actual_quantity,
            stock_before=stock_before,
            stock_after=material.stock,
            related_id=borrow.id,
            related_type='borrow',
            remark=f'归还借用: {borrow.borrow_no}. {remark}'
        )
        db.session.add(record)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '归还成功',
        'data': borrow.to_dict()
    })


@borrow_bp.route('/<int:id>/mark-overdue', methods=['POST'])
@admin_required
def mark_overdue(id):
    """标记借用逾期（管理员）"""
    borrow = BorrowRecord.query.get_or_404(id)
    
    if borrow.status != 'active':
        return jsonify({'success': False, 'message': '只能标记进行中的借用'}), 400
    
    borrow.status = 'overdue'
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '已标记为逾期',
        'data': borrow.to_dict()
    })


@borrow_bp.route('/overdue-check', methods=['POST'])
@admin_required
def check_overdue():
    """检查逾期借用（管理员）"""
    today = datetime.utcnow().date()
    
    # 查找已逾期但未标记的记录
    overdue_records = BorrowRecord.query.filter(
        BorrowRecord.status == 'active',
        BorrowRecord.expected_return_date < today
    ).all()
    
    count = 0
    for record in overdue_records:
        record.status = 'overdue'
        count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'已标记 {count} 条逾期记录',
        'data': {
            'overdue_count': count,
            'records': [r.to_dict() for r in overdue_records]
        }
    })


@borrow_bp.route('/my-borrows', methods=['GET'])
@jwt_required()
def get_my_borrows():
    """获取我的借用记录"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    
    query = BorrowRecord.query.filter(
        BorrowRecord.user_id == get_current_user_id()
    )
    
    if status:
        query = query.filter(BorrowRecord.status == status)
    
    query = query.order_by(BorrowRecord.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'data': {
            'items': [r.to_dict() for r in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }
    })
