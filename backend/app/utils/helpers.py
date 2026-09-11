"""
辅助工具函数
"""
from datetime import datetime


def generate_code(prefix=''):
    """
    生成编号
    格式: 前缀 + 年月日 + 4位序号
    例如: M202401150001, I202401150001
    """
    from app import db
    from app.models import Material, MaterialBatch, OperationRecord, PurchaseRequest, BorrowRecord

    today = datetime.now().strftime('%Y%m%d')

    # 根据前缀确定查询哪个模型
    model_map = {
        'M': Material,
        'I': OperationRecord,
        'O': OperationRecord,
        'P': PurchaseRequest,
        'B': BorrowRecord,
        'A': OperationRecord,
        'BT': MaterialBatch,
    }
    
    model = model_map.get(prefix, Material)
    code_field = 'code' if prefix == 'M' else 'operation_no' if prefix in ['I', 'O', 'A'] else 'request_no' if prefix == 'P' else 'borrow_no'
    
    # 查询今日最后一个编号
    today_prefix = f'{prefix}{today}'
    
    if prefix == 'M':
        last = model.query.filter(
            model.code.like(f'{today_prefix}%')
        ).order_by(model.code.desc()).first()
    elif prefix in ['I', 'O', 'A']:
        last = model.query.filter(
            model.operation_no.like(f'{today_prefix}%')
        ).order_by(model.operation_no.desc()).first()
    elif prefix == 'P':
        last = model.query.filter(
            model.request_no.like(f'{today_prefix}%')
        ).order_by(model.request_no.desc()).first()
    elif prefix == 'BT':
        last = model.query.filter(
            model.batch_no.like(f'{today_prefix}%')
        ).order_by(model.batch_no.desc()).first()
    else:
        last = model.query.filter(
            model.borrow_no.like(f'{today_prefix}%')
        ).order_by(model.borrow_no.desc()).first()
    
    # 生成序号
    if last:
        if prefix == 'M':
            last_num = int(last.code[-4:])
        elif prefix in ['I', 'O', 'A']:
            last_num = int(last.operation_no[-4:])
        elif prefix == 'P':
            last_num = int(last.request_no[-4:])
        elif prefix == 'BT':
            last_num = int(last.batch_no[-4:])
        else:
            last_num = int(last.borrow_no[-4:])
        new_num = last_num + 1
    else:
        new_num = 1
    
    return f'{today_prefix}{new_num:04d}'


def paginate(query, page=1, per_page=20):
    """
    分页辅助函数
    """
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': pagination.items,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    }


def format_datetime(dt, format='%Y-%m-%d %H:%M:%S'):
    """
    格式化日期时间
    """
    if dt:
        return dt.strftime(format)
    return None


def safe_int(value, default=0):
    """
    安全转换为整数
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """
    安全转换为浮点数
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
