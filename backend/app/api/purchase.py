"""
采购申请API
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app import db
from app.models import PurchaseRequest, Material, OperationRecord
from app.api.auth import admin_required, get_current_user_id
from app.api.alerts import sync_material_alert
from app.utils.helpers import generate_code

purchase_bp = Blueprint('purchase', __name__)


def find_matching_material(material_name, spec=None, category_id=None):
    query = Material.query.filter(Material.name == material_name)
    if spec:
        query = query.filter(Material.spec == spec)
    if category_id:
        query = query.filter(Material.category_id == category_id)
    return query.first()


@purchase_bp.route('', methods=['GET'])
@jwt_required()
def get_purchase_requests():
    """获取采购申请列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    my_requests = request.args.get('my', 'false').lower() == 'true'
    role = get_jwt().get('role')
    
    query = PurchaseRequest.query
    
    # 访问者只能查看自己的申请；管理员可查看全部或按my=true查看自己
    if role != 'admin' or my_requests:
        query = query.filter(PurchaseRequest.user_id == get_current_user_id())
    
    if status:
        query = query.filter(PurchaseRequest.status == status)
    
    query = query.order_by(PurchaseRequest.created_at.desc())
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


@purchase_bp.route('/summary', methods=['GET'])
@admin_required
def get_purchase_summary():
    """获取管理员采购提醒统计"""
    pending = PurchaseRequest.query.filter_by(status='pending').count()
    approved = PurchaseRequest.query.filter_by(status='approved').count()
    latest = PurchaseRequest.query.filter(
        PurchaseRequest.status.in_(['pending', 'approved'])
    ).order_by(PurchaseRequest.created_at.desc()).limit(5).all()

    return jsonify({
        'success': True,
        'data': {
            'pending': pending,
            'approved': approved,
            'total_attention': pending + approved,
            'latest': [item.to_dict() for item in latest]
        }
    })


@purchase_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_purchase_request(id):
    """获取采购申请详情"""
    request_obj = PurchaseRequest.query.get_or_404(id)
    if get_jwt().get('role') != 'admin' and request_obj.user_id != get_current_user_id():
        return jsonify({'success': False, 'message': '无权访问'}), 403
    return jsonify({
        'success': True,
        'data': request_obj.to_dict()
    })


@purchase_bp.route('', methods=['POST'])
@jwt_required()
def create_purchase_request():
    """创建采购申请"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    # 必填字段验证
    required_fields = ['material_name', 'quantity', 'reason']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field}不能为空'}), 400
    
    material_id = data.get('material_id')
    if not material_id:
        matched_material = find_matching_material(
            data['material_name'],
            data.get('spec', ''),
            data.get('category_id')
        )
        material_id = matched_material.id if matched_material else None

    # 创建采购申请
    purchase = PurchaseRequest(
        request_no=generate_code('P'),
        user_id=get_current_user_id(),
        material_id=material_id,
        material_name=data['material_name'],
        category_id=data.get('category_id'),
        spec=data.get('spec', ''),
        quantity=data['quantity'],
        supplier_link=data.get('supplier_link', ''),
        estimated_price=data.get('estimated_price'),
        reason=data['reason'],
        remark=data.get('remark', '')
    )
    
    db.session.add(purchase)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '采购申请提交成功',
        'data': purchase.to_dict()
    }), 201


@purchase_bp.route('/<int:id>/approve', methods=['POST', 'PUT'])
@admin_required
def approve_purchase(id):
    """审批采购申请（管理员）"""
    purchase = PurchaseRequest.query.get_or_404(id)
    
    if purchase.status != 'pending':
        return jsonify({'success': False, 'message': '该申请已处理'}), 400
    
    data = request.get_json()
    action = data.get('action')  # approve 或 reject
    remark = data.get('remark', '')
    
    if action not in ['approve', 'reject']:
        return jsonify({'success': False, 'message': '操作类型错误'}), 400
    
    purchase.status = 'approved' if action == 'approve' else 'rejected'
    purchase.approver_id = get_current_user_id()
    purchase.approved_at = db.func.now()
    purchase.approval_remark = remark
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '审批完成',
        'data': purchase.to_dict()
    })


@purchase_bp.route('/<int:id>/complete', methods=['POST'])
@admin_required
def complete_purchase(id):
    """完成采购并入库（管理员）"""
    purchase = PurchaseRequest.query.get_or_404(id)
    
    if purchase.status != 'approved':
        return jsonify({'success': False, 'message': '该申请未通过审批'}), 400
    
    data = request.get_json() or {}
    actual_quantity = data.get('actual_quantity', purchase.quantity)
    
    # 更新申请状态
    purchase.status = 'completed'
    
    material = Material.query.get(purchase.material_id) if purchase.material_id else None
    if not material:
        material = find_matching_material(purchase.material_name, purchase.spec, purchase.category_id)

    if material:
        from app.api.inventory import create_batch
        stock_before = material.stock
        material.stock += actual_quantity
        material.update_status()
        sync_material_alert(material)
        purchase.material_id = material.id
        try:
            batch = create_batch(material, data, actual_quantity)
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 400

        record = OperationRecord(
            operation_no=generate_code('I'),
            type='in',
            user_id=get_current_user_id(),
            material_id=material.id,
            material_name=material.name,
            quantity=actual_quantity,
            stock_before=stock_before,
            stock_after=material.stock,
            related_id=purchase.id,
            related_type='purchase',
            remark=f'采购入库: {purchase.request_no}'
        )
        db.session.add(record)
    else:
        # 创建新物料
        material = Material(
            code=generate_code('M'),
            name=purchase.material_name,
            category_id=purchase.category_id,
            spec=purchase.spec,
            stock=actual_quantity,
            threshold=10,  # 默认阈值
            remark=f'采购入库: {purchase.request_no}'
        )
        material.update_status()
        db.session.add(material)
        db.session.flush()
        from app.api.inventory import create_batch
        try:
            batch = create_batch(material, data, actual_quantity)
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 400
        
        # 更新采购申请关联的物料ID
        purchase.material_id = material.id
        
        # 创建入库记录
        record = OperationRecord(
            operation_no=generate_code('I'),
            type='in',
            user_id=get_current_user_id(),
            material_id=material.id,
            material_name=material.name,
            quantity=actual_quantity,
            stock_before=0,
            stock_after=actual_quantity,
            related_id=purchase.id,
            related_type='purchase',
            remark=f'新物料采购入库: {purchase.request_no}'
        )
        db.session.add(record)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '采购完成并已入库',
        'data': {**purchase.to_dict(), 'batch': batch.to_dict()}
    })


@purchase_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def cancel_purchase_request(id):
    """取消采购申请"""
    purchase = PurchaseRequest.query.get_or_404(id)
    
    # 只能取消自己的申请
    if purchase.user_id != get_current_user_id():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    if purchase.status != 'pending':
        return jsonify({'success': False, 'message': '只能取消待审批的申请'}), 400
    
    db.session.delete(purchase)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '申请已取消'
    })


@purchase_bp.route('/<int:id>/cancel', methods=['PUT', 'POST'])
@jwt_required()
def cancel_purchase_request_compat(id):
    """兼容前端旧调用的取消采购申请接口"""
    return cancel_purchase_request(id)
