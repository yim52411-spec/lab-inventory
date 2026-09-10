"""
历史记录API
"""
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from sqlalchemy import or_
from datetime import datetime
import json
import io
from app import db
from app.models import OperationRecord, PurchaseRequest, BorrowRecord

records_bp = Blueprint('records', __name__)


@records_bp.route('', methods=['GET'])
@jwt_required()
def get_records():
    """获取综合历史记录"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    record_type = request.args.get('type', '')  # inventory, purchase, borrow
    keyword = request.args.get('keyword', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # 默认返回出入库记录
    if not record_type or record_type == 'inventory':
        query = OperationRecord.query
        
        if keyword:
            query = query.filter(
                or_(
                    OperationRecord.material_name.contains(keyword),
                    OperationRecord.operation_no.contains(keyword)
                )
            )
        
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
                'per_page': per_page,
                'type': 'inventory'
            }
        })
    
    elif record_type == 'purchase':
        query = PurchaseRequest.query
        
        if keyword:
            query = query.filter(
                or_(
                    PurchaseRequest.material_name.contains(keyword),
                    PurchaseRequest.request_no.contains(keyword)
                )
            )
        
        if start_date:
            query = query.filter(PurchaseRequest.created_at >= start_date)
        
        if end_date:
            query = query.filter(PurchaseRequest.created_at <= end_date + ' 23:59:59')
        
        query = query.order_by(PurchaseRequest.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'data': {
                'items': [r.to_dict() for r in pagination.items],
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page,
                'per_page': per_page,
                'type': 'purchase'
            }
        })
    
    elif record_type == 'borrow':
        query = BorrowRecord.query
        
        if keyword:
            query = query.filter(
                or_(
                    BorrowRecord.borrow_no.contains(keyword)
                )
            )
        
        if start_date:
            query = query.filter(BorrowRecord.created_at >= start_date)
        
        if end_date:
            query = query.filter(BorrowRecord.created_at <= end_date + ' 23:59:59')
        
        query = query.order_by(BorrowRecord.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'data': {
                'items': [r.to_dict() for r in pagination.items],
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page,
                'per_page': per_page,
                'type': 'borrow'
            }
        })
    
    return jsonify({
        'success': False,
        'message': '无效的记录类型'
    }), 400


@records_bp.route('/export', methods=['GET'])
@jwt_required()
def export_records():
    """导出历史记录"""
    record_type = request.args.get('type', 'inventory')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    data = []
    filename_prefix = ''
    
    if record_type == 'inventory':
        query = OperationRecord.query
        filename_prefix = '出入库记录'
        
        if start_date:
            query = query.filter(OperationRecord.created_at >= start_date)
        if end_date:
            query = query.filter(OperationRecord.created_at <= end_date + ' 23:59:59')
        
        records = query.order_by(OperationRecord.created_at.desc()).all()
        data = [r.to_dict() for r in records]
    
    elif record_type == 'purchase':
        query = PurchaseRequest.query
        filename_prefix = '采购申请记录'
        
        if start_date:
            query = query.filter(PurchaseRequest.created_at >= start_date)
        if end_date:
            query = query.filter(PurchaseRequest.created_at <= end_date + ' 23:59:59')
        
        records = query.order_by(PurchaseRequest.created_at.desc()).all()
        data = [r.to_dict() for r in records]
    
    elif record_type == 'borrow':
        query = BorrowRecord.query
        filename_prefix = '借用记录'
        
        if start_date:
            query = query.filter(BorrowRecord.created_at >= start_date)
        if end_date:
            query = query.filter(BorrowRecord.created_at <= end_date + ' 23:59:59')
        
        records = query.order_by(BorrowRecord.created_at.desc()).all()
        data = [r.to_dict() for r in records]
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{filename_prefix}_{timestamp}.json'
    
    # 创建JSON文件
    json_data = json.dumps(data, ensure_ascii=False, indent=2)
    buffer = io.BytesIO(json_data.encode('utf-8'))
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )


@records_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """获取仪表盘统计数据"""
    from sqlalchemy import func
    from app.models import Material, User
    
    # 物料统计
    total_materials = Material.query.count()
    normal_materials = Material.query.filter_by(status='normal').count()
    warning_materials = Material.query.filter_by(status='warning').count()
    danger_materials = Material.query.filter_by(status='danger').count()
    
    # 今日操作统计
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    today_in = OperationRecord.query.filter(
        OperationRecord.type == 'in',
        OperationRecord.created_at >= today_start
    ).count()
    
    today_out = OperationRecord.query.filter(
        OperationRecord.type == 'out',
        OperationRecord.created_at >= today_start
    ).count()
    
    # 最近活动
    recent_records = OperationRecord.query.order_by(
        OperationRecord.created_at.desc()
    ).limit(10).all()
    
    # 待处理申请
    pending_purchases = PurchaseRequest.query.filter_by(status='pending').count()
    active_borrows = BorrowRecord.query.filter_by(status='active').count()
    overdue_borrows = BorrowRecord.query.filter_by(status='overdue').count()

    purchase_trend = {}
    for item in PurchaseRequest.query.order_by(PurchaseRequest.created_at.asc()).all():
        month = item.created_at.strftime('%Y-%m')
        current = purchase_trend.setdefault(month, {'month': month, 'quantity': 0, 'amount': 0})
        current['quantity'] += item.quantity or 0
        current['amount'] += float(item.quantity or 0) * float(item.estimated_price or 0)
    
    return jsonify({
        'success': True,
        'data': {
            'material_stats': {
                'total': total_materials,
                'normal': normal_materials,
                'warning': warning_materials,
                'danger': danger_materials
            },
            'today_operations': {
                'in': today_in,
                'out': today_out
            },
            'pending_tasks': {
                'purchase_requests': pending_purchases,
                'active_borrows': active_borrows,
                'overdue_borrows': overdue_borrows
            },
            'recent_activities': [r.to_dict() for r in recent_records]
            , 'purchase_trend': list(purchase_trend.values())[-12:]
        }
    })
