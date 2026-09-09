"""
出入库管理API
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.models import Material, OperationRecord, PurchaseRequest
from app.api.auth import admin_required, get_current_user_id
from app.api.alerts import sync_material_alert
from app.utils.helpers import generate_code

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/in', methods=['POST'])
@admin_required
def stock_in():
    """入库操作（管理员）"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    material_id = data.get('material_id')
    quantity = data.get('quantity')
    
    if not material_id or not quantity:
        return jsonify({'success': False, 'message': '物料ID和数量不能为空'}), 400
    
    if quantity <= 0:
        return jsonify({'success': False, 'message': '入库数量必须大于0'}), 400
    
    material = Material.query.get(material_id)
    if not material:
        return jsonify({'success': False, 'message': '物料不存在'}), 404

    matched_purchase = None
    if data.get('related_type') == 'purchase' and not data.get('related_id'):
        matched_purchase = PurchaseRequest.query.filter_by(
            material_id=material.id,
            status='approved'
        ).order_by(PurchaseRequest.approved_at.asc()).first()
        if not matched_purchase:
            matched_purchase = PurchaseRequest.query.filter(
                PurchaseRequest.status == 'approved',
                PurchaseRequest.material_id.is_(None),
                PurchaseRequest.material_name == material.name,
                PurchaseRequest.spec == (material.spec or '')
            ).order_by(PurchaseRequest.approved_at.asc()).first()
    
    # 记录入库前库存
    stock_before = material.stock
    
    # 更新库存
    material.stock += quantity
    material.update_status()
    sync_material_alert(material)

    related_id = data.get('related_id')
    related_type = data.get('related_type')
    remark = data.get('remark', '')

    if matched_purchase:
        matched_purchase.status = 'completed'
        related_id = matched_purchase.id
        related_type = 'purchase'
        remark = remark or f'手动入库自动关联采购申请: {matched_purchase.request_no}'
    
    # 创建操作记录
    record = OperationRecord(
        operation_no=generate_code('I'),
        type='in',
        user_id=get_current_user_id(),
        material_id=material.id,
        material_name=material.name,
        quantity=quantity,
        stock_before=stock_before,
        stock_after=material.stock,
        related_id=related_id,
        related_type=related_type,
        remark=remark
    )
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '入库成功',
        'data': {
            'material': material.to_dict(),
            'record': record.to_dict(),
            'matched_purchase': matched_purchase.to_dict() if matched_purchase else None
        }
    })


@inventory_bp.route('/out', methods=['POST'])
@admin_required
def stock_out():
    """出库操作（管理员）"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    material_id = data.get('material_id')
    quantity = data.get('quantity')
    
    if not material_id or not quantity:
        return jsonify({'success': False, 'message': '物料ID和数量不能为空'}), 400
    
    if quantity <= 0:
        return jsonify({'success': False, 'message': '出库数量必须大于0'}), 400
    
    material = Material.query.get(material_id)
    if not material:
        return jsonify({'success': False, 'message': '物料不存在'}), 404
    
    if material.stock < quantity:
        return jsonify({
            'success': False,
            'message': f'库存不足，当前库存: {material.stock}'
        }), 400
    
    # 记录出库前库存
    stock_before = material.stock
    
    # 更新库存
    material.stock -= quantity
    material.update_status()
    sync_material_alert(material)
    
    # 创建操作记录
    record = OperationRecord(
        operation_no=generate_code('O'),
        type='out',
        user_id=get_current_user_id(),
        material_id=material.id,
        material_name=material.name,
        quantity=-quantity,  # 出库为负数
        stock_before=stock_before,
        stock_after=material.stock,
        related_id=data.get('related_id'),
        related_type=data.get('related_type'),
        remark=data.get('remark', '')
    )
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '出库成功',
        'data': {
            'material': material.to_dict(),
            'record': record.to_dict()
        }
    })


@inventory_bp.route('/adjust', methods=['POST'])
@admin_required
def stock_adjust():
    """库存调整（管理员）"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    material_id = data.get('material_id')
    new_stock = data.get('new_stock')
    reason = data.get('reason', '')
    
    if not material_id or new_stock is None:
        return jsonify({'success': False, 'message': '物料ID和新库存不能为空'}), 400
    
    if new_stock < 0:
        return jsonify({'success': False, 'message': '库存不能为负数'}), 400
    
    material = Material.query.get(material_id)
    if not material:
        return jsonify({'success': False, 'message': '物料不存在'}), 404
    
    # 记录调整前库存
    stock_before = material.stock
    
    # 更新库存
    material.stock = new_stock
    material.update_status()
    sync_material_alert(material)
    
    # 创建操作记录
    record = OperationRecord(
        operation_no=generate_code('A'),
        type='adjust',
        user_id=get_current_user_id(),
        material_id=material.id,
        material_name=material.name,
        quantity=new_stock - stock_before,
        stock_before=stock_before,
        stock_after=material.stock,
        remark=f'库存调整: {reason}'
    )
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '库存调整成功',
        'data': {
            'material': material.to_dict(),
            'record': record.to_dict()
        }
    })


@inventory_bp.route('/records', methods=['GET'])
@jwt_required()
def get_records():
    """获取出入库记录"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    operation_type = request.args.get('type', '')
    material_id = request.args.get('material_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = OperationRecord.query
    
    if operation_type:
        query = query.filter(OperationRecord.type == operation_type)
    
    if material_id:
        query = query.filter(OperationRecord.material_id == material_id)
    
    if start_date:
        query = query.filter(OperationRecord.created_at >= start_date)
    
    if end_date:
        query = query.filter(OperationRecord.created_at <= end_date + ' 23:59:59')
    
    query = query.order_by(OperationRecord.created_at.desc())
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


@inventory_bp.route('/records/<int:id>', methods=['GET'])
@jwt_required()
def get_record(id):
    """获取单条记录详情"""
    record = OperationRecord.query.get_or_404(id)
    return jsonify({
        'success': True,
        'data': record.to_dict()
    })
