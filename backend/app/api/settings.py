"""
系统设置API
"""
import os
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import SystemSetting, Material, OperationRecord, PurchaseRequest, BorrowRecord
from app.api.auth import admin_required

settings_bp = Blueprint('settings', __name__)


DEFAULT_SETTINGS = {
    'alert_email': ('admin@lab.com', '库存预警邮件接收地址'),
    'alert_check_interval': ('30', '预警检查频率，单位分钟'),
    'alert_email_enabled': ('true', '库存不足或预警时发送邮件'),
    'overdue_email_enabled': ('false', '借用逾期时发送邮件'),
    'storage_location': ('cloud', '数据存储位置'),
    'backup_frequency': ('daily', '自动备份频率'),
    'last_backup_at': ('', '最近一次数据库备份时间')
}


def get_setting_value(key):
    setting = SystemSetting.query.filter_by(key=key).first()
    if setting:
        return setting.value
    default = DEFAULT_SETTINGS.get(key)
    return default[0] if default else None


def set_setting_value(key, value):
    setting = SystemSetting.query.filter_by(key=key).first()
    if not setting:
        setting = SystemSetting(
            key=key,
            description=DEFAULT_SETTINGS.get(key, ('', ''))[1]
        )
        db.session.add(setting)
    setting.value = str(value)


def get_sqlite_database_path():
    database_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not database_uri.startswith('sqlite:///'):
        return None
    return database_uri.replace('sqlite:///', '', 1)


def create_excel_backup(reason='manual'):
    backend_dir = os.path.dirname(current_app.root_path)
    backup_dir = os.path.join(backend_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)

    def add_sheet(title, headers, rows):
        sheet = workbook.create_sheet(title)
        sheet.append(headers)
        for row in rows:
            sheet.append(row)

    add_sheet('库存管理', [
        '物料编号', '物料名称', '分类', '规格', '库存数量', '单位', '预警阈值', '存放位置', '状态', '备注', '创建时间'
    ], [[
        item.code,
        item.name,
        item.category.name if item.category else '',
        item.spec or '',
        item.stock,
        item.unit,
        item.threshold,
        item.location or '',
        item.status,
        item.remark or '',
        item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else ''
    ] for item in Material.query.order_by(Material.created_at.desc()).all()])

    add_sheet('出入库记录', [
        '操作单号', '类型', '物料名称', '数量', '操作前库存', '操作后库存', '操作人', '关联类型', '关联ID', '备注', '时间'
    ], [[
        item.operation_no,
        item.get_type_name(),
        item.material_name or (item.material.name if item.material else ''),
        item.quantity,
        item.stock_before,
        item.stock_after,
        item.operator.name if item.operator else '',
        item.related_type or '',
        item.related_id or '',
        item.remark or '',
        item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else ''
    ] for item in OperationRecord.query.order_by(OperationRecord.created_at.desc()).all()])

    add_sheet('采购申请', [
        '申请单号', '申请人', '物料名称', '规格', '数量', '预计单价', '采购链接', '申请理由', '备注', '状态', '审批人', '审批备注', '审批时间', '提交时间'
    ], [[
        item.request_no,
        item.requester.name if item.requester else '',
        item.material_name,
        item.spec or '',
        item.quantity,
        float(item.estimated_price) if item.estimated_price else '',
        item.supplier_link or '',
        item.reason or '',
        item.remark or '',
        item.status,
        item.approver.name if item.approver else '',
        item.approval_remark or '',
        item.approved_at.strftime('%Y-%m-%d %H:%M:%S') if item.approved_at else '',
        item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else ''
    ] for item in PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).all()])

    add_sheet('借用记录', [
        '借用单号', '借用人', '物料名称', '数量', '借用理由', '状态', '借用时间', '预计归还', '实际归还'
    ], [[
        item.borrow_no,
        item.borrower.name if item.borrower else '',
        item.material.name if item.material else '',
        item.quantity,
        item.reason or '',
        item.status,
        item.borrow_date.strftime('%Y-%m-%d %H:%M:%S') if item.borrow_date else '',
        item.expected_return_date.strftime('%Y-%m-%d') if item.expected_return_date else '',
        item.actual_return_date.strftime('%Y-%m-%d %H:%M:%S') if item.actual_return_date else ''
    ] for item in BorrowRecord.query.order_by(BorrowRecord.created_at.desc()).all()])

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f'lab_inventory_{reason}_{timestamp}.xlsx'
    backup_path = os.path.join(backup_dir, backup_name)
    db.session.commit()
    workbook.save(backup_path)
    set_setting_value('last_backup_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    db.session.commit()
    return backup_path, None


def ensure_scheduled_backup():
    frequency = get_setting_value('backup_frequency') or 'daily'
    last_backup_at = get_setting_value('last_backup_at')
    if not last_backup_at:
        create_excel_backup('auto')
        return

    try:
        last_backup = datetime.strptime(last_backup_at, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return

    intervals = {
        'daily': timedelta(days=1),
        'weekly': timedelta(days=7),
        'monthly': timedelta(days=30)
    }
    if datetime.now() - last_backup >= intervals.get(frequency, timedelta(days=1)):
        create_excel_backup('auto')


@settings_bp.route('', methods=['GET'])
@admin_required
def get_settings():
    """获取系统设置"""
    for key, (value, description) in DEFAULT_SETTINGS.items():
        existing = SystemSetting.query.filter_by(key=key).first()
        if not existing:
            db.session.add(SystemSetting(key=key, value=value, description=description))
    db.session.commit()
    ensure_scheduled_backup()

    settings = SystemSetting.query.order_by(SystemSetting.key.asc()).all()
    data = {item.key: item.value for item in settings}
    data['database_uri'] = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    data['database_note'] = '系统数据实时写入当前后端数据库；阿里云部署建议使用 MySQL DATABASE_URL。'

    return jsonify({'success': True, 'data': data})


@settings_bp.route('', methods=['PUT'])
@admin_required
def update_settings():
    """更新系统设置"""
    data = request.get_json() or {}
    allowed_keys = set(DEFAULT_SETTINGS.keys())

    for key, value in data.items():
        if key not in allowed_keys:
            continue

        setting = SystemSetting.query.filter_by(key=key).first()
        if not setting:
            setting = SystemSetting(
                key=key,
                description=DEFAULT_SETTINGS[key][1]
            )
            db.session.add(setting)
        setting.value = str(value)

    db.session.commit()

    return jsonify({'success': True, 'message': '系统设置已保存'})


@settings_bp.route('/backup', methods=['POST'])
@admin_required
def backup_now():
    """立即导出 Excel 数据备份"""
    backup_path, error = create_excel_backup('manual')
    if error:
        return jsonify({'success': False, 'message': error}), 400

    return jsonify({
        'success': True,
        'message': 'Excel数据备份已生成',
        'data': {
            'backup_path': backup_path,
            'last_backup_at': get_setting_value('last_backup_at')
        }
    })
