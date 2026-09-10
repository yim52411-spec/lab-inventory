"""
库存预警API
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import and_
from datetime import datetime, timedelta, date
from app import db, mail
from app.models import Alert, Material, MaterialBatch, User, SystemSetting
from app.api.auth import admin_required
from flask_mail import Message

alerts_bp = Blueprint('alerts', __name__)


def sync_material_alert(material):
    """Keep unresolved stock alerts aligned with the material's current stock."""
    unresolved = Alert.query.filter_by(material_id=material.id, alert_type='stock_low', is_resolved=False).all()

    if material.stock > material.threshold:
        for alert in unresolved:
            alert.is_resolved = True
            alert.resolved_at = datetime.utcnow()
        return None

    level = 'danger' if material.stock <= 0 else 'warning'
    if unresolved:
        alert = unresolved[0]
        alert.level = level
        alert.current_stock = material.stock
        alert.threshold = material.threshold
        return alert

    alert = Alert(
        material_id=material.id,
        alert_type='stock_low',
        level=level,
        current_stock=material.stock,
        threshold=material.threshold
    )
    db.session.add(alert)
    return alert


def sync_batch_expiry_alert(batch, today=None):
    """按批次剩余库存和到期日期同步提前30天的到期预警。"""
    alerts = Alert.query.filter_by(batch_id=batch.id, alert_type='expiry', is_resolved=False).all()
    today = today or date.today()
    should_alert = bool(
        batch.quantity_remaining > 0 and batch.expiry_date and
        today >= batch.expiry_date - timedelta(days=30)
    )
    if not should_alert:
        for alert in alerts:
            alert.is_resolved = True
            alert.resolved_at = datetime.utcnow()
        return None

    level = 'danger' if today >= batch.expiry_date else 'warning'
    alert = alerts[0] if alerts else Alert(
        material_id=batch.material_id,
        batch_id=batch.id,
        alert_type='expiry',
        current_stock=batch.quantity_remaining,
        threshold=0,
    )
    alert.level = level
    alert.current_stock = batch.quantity_remaining
    alert.threshold = 0
    if not alerts:
        db.session.add(alert)
    return alert


def sync_all_alerts():
    new_alerts = []
    for material in Material.query.all():
        before = Alert.query.filter_by(material_id=material.id, alert_type='stock_low', is_resolved=False).first()
        alert = sync_material_alert(material)
        if alert and not before:
            new_alerts.append(alert)
        for batch in material.batches.all():
            before = Alert.query.filter_by(batch_id=batch.id, alert_type='expiry', is_resolved=False).first()
            alert = sync_batch_expiry_alert(batch)
            if alert and not before:
                new_alerts.append(alert)
    return new_alerts


def get_setting(key, default=None):
    setting = SystemSetting.query.filter_by(key=key).first()
    return setting.value if setting else default


def get_alert_recipients():
    configured = get_setting('alert_email', '')
    recipients = [email.strip() for email in configured.split(',') if email.strip()]
    if recipients:
        return recipients

    admins = User.query.filter_by(role='admin', is_active=True).all()
    return [a.email for a in admins if a.email]


def mail_is_configured():
    return bool(
        current_app.config.get('MAIL_SERVER')
        and current_app.config.get('MAIL_USERNAME')
        and current_app.config.get('MAIL_PASSWORD')
        and current_app.config.get('MAIL_DEFAULT_SENDER')
    )


@alerts_bp.route('/mail-status', methods=['GET'])
@admin_required
def get_mail_status():
    """返回邮件发送链路的非敏感诊断信息，不发送测试邮件。"""
    scheduler = current_app.extensions.get('scheduler')
    return jsonify({
        'success': True,
        'data': {
            'configured': mail_is_configured(),
            'enabled': get_setting('alert_email_enabled', 'true') == 'true',
            'server': current_app.config.get('MAIL_SERVER'),
            'port': current_app.config.get('MAIL_PORT'),
            'mode': 'SSL' if current_app.config.get('MAIL_USE_SSL') else ('STARTTLS' if current_app.config.get('MAIL_USE_TLS') else 'plain'),
            'username': current_app.config.get('MAIL_USERNAME') or '',
            'recipients': get_alert_recipients(),
            'unsent_alerts': Alert.query.filter_by(is_sent=False, is_resolved=False).count(),
            'last_alert_check_at': get_setting('last_alert_check_at', ''),
            'scheduler_running': bool(scheduler and scheduler.running)
        }
    })


def send_pending_alert_emails():
    """发送当前未发送的预警；供接口和后台调度器复用。"""
    unsent_alerts = Alert.query.filter_by(is_sent=False, is_resolved=False).all()
    recipients = get_alert_recipients()
    if not unsent_alerts or not recipients or not mail_is_configured():
        return 0
    subject = f'【库存预警】{len(unsent_alerts)} 条物料预警通知'
    body = '<h2>库存预警通知</h2><table border="1" cellpadding="10">'
    body += '<tr><th>物料编号</th><th>物料名称</th><th>批次</th><th>剩余库存</th><th>到期日期</th><th>类型</th><th>级别</th></tr>'
    for alert in unsent_alerts:
        material = alert.material
        alert.is_sent = True
        alert.sent_at = datetime.utcnow()
        body += (
            f'<tr><td>{material.code}</td><td>{material.name}</td>'
            f'<td>{alert.batch.batch_no if alert.batch else "-"}</td>'
            f'<td>{alert.current_stock}</td>'
            f'<td>{alert.batch.expiry_date if alert.batch else "-"}</td>'
            f'<td>{"到期预警" if alert.alert_type == "expiry" else "库存预警"}</td>'
            f'<td>{alert.level}</td></tr>'
        )
    body += '</table><p>请登录系统查看详情并及时处理。</p>'
    try:
        mail.send(Message(subject=subject, recipients=recipients, html=body))
        db.session.commit()
        return len(unsent_alerts)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('预警邮件发送失败')
        return 0


@alerts_bp.route('', methods=['GET'])
@jwt_required()
def get_alerts():
    """获取预警列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    level = request.args.get('level', '')
    is_resolved = request.args.get('is_resolved')
    
    query = Alert.query
    
    if level:
        query = query.filter(Alert.level == level)
    
    if is_resolved is not None:
        is_resolved_bool = is_resolved.lower() == 'true'
        query = query.filter(Alert.is_resolved == is_resolved_bool)
    
    query = query.order_by(Alert.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'data': {
            'items': [a.to_dict() for a in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }
    })


@alerts_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_alert_stats():
    """获取预警统计"""
    total = Alert.query.count()
    warning = Alert.query.filter_by(level='warning', is_resolved=False).count()
    danger = Alert.query.filter_by(level='danger', is_resolved=False).count()
    resolved = Alert.query.filter_by(is_resolved=True).count()
    unsent = Alert.query.filter_by(is_sent=False, is_resolved=False).count()
    
    # 今日预警
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_alerts = Alert.query.filter(Alert.created_at >= today_start).count()
    
    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'warning': warning,
            'danger': danger,
            'resolved': resolved,
            'unsent': unsent,
            'today': today_alerts
        }
    })


@alerts_bp.route('/check', methods=['POST'])
@admin_required
def check_alerts():
    """手动检查库存预警（管理员）"""
    new_alerts = []

    new_alerts = sync_all_alerts()
    
    db.session.commit()

    email_status = 'disabled'
    if get_setting('alert_email_enabled', 'true') == 'true' and new_alerts:
        if mail_is_configured():
            sent_count = send_pending_alert_emails()
            email_status = f'已发送 {sent_count} 条预警邮件'
        else:
            email_status = '邮件未发送：SMTP账号、密码或默认发件人未配置'
    
    return jsonify({
        'success': True,
        'message': f'发现 {len(new_alerts)} 条新预警',
        'data': [a.to_dict() for a in new_alerts],
        'email_status': email_status
    })


@alerts_bp.route('/send-emails', methods=['POST'])
@admin_required
def send_alert_emails():
    """发送预警邮件（管理员）"""
    if not current_app.config.get('ALERT_EMAIL_ENABLED'):
        return jsonify({
            'success': False,
            'message': '邮件功能未启用'
        }), 400
    
    # 获取未发送的预警
    unsent_alerts = Alert.query.filter_by(is_sent=False, is_resolved=False).all()
    
    if not unsent_alerts:
        return jsonify({
            'success': True,
            'message': '没有待发送的预警'
        })
    
    # 获取系统设置中的预警接收邮箱，未配置时退回管理员邮箱
    admin_emails = get_alert_recipients()
    
    if not admin_emails:
        return jsonify({
            'success': False,
            'message': '没有配置预警邮件接收地址'
        }), 400

    if not mail_is_configured():
        return jsonify({
            'success': False,
            'message': 'SMTP未配置完整，无法发送邮件'
        }), 400
    
    sent_count = send_pending_alert_emails()
    if not sent_count:
        return jsonify({'success': False, 'message': '邮件发送失败，请检查SMTP配置和日志'}), 500
    
    return jsonify({
        'success': True,
        'message': f'成功发送 {sent_count} 条预警邮件',
        'data': {
            'sent_count': sent_count,
            'recipients': admin_emails
        }
    })


@alerts_bp.route('/<int:id>/resolve', methods=['POST'])
@admin_required
def resolve_alert(id):
    """解决预警（管理员）"""
    alert = Alert.query.get_or_404(id)
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '预警已标记为已解决',
        'data': alert.to_dict()
    })


@alerts_bp.route('/settings', methods=['GET'])
@admin_required
def get_alert_settings():
    """获取预警设置（管理员）"""
    return jsonify({
        'success': True,
        'data': {
            'check_interval': current_app.config.get('ALERT_CHECK_INTERVAL', 30),
            'email_enabled': get_setting('alert_email_enabled', 'true') == 'true',
            'alert_email': get_setting('alert_email', ''),
            'mail_server': current_app.config.get('MAIL_SERVER'),
            'mail_port': current_app.config.get('MAIL_PORT'),
            'mail_use_tls': current_app.config.get('MAIL_USE_TLS'),
            'mail_use_ssl': current_app.config.get('MAIL_USE_SSL'),
            'mail_username': current_app.config.get('MAIL_USERNAME'),
            'mail_default_sender': current_app.config.get('MAIL_DEFAULT_SENDER')
        }
    })


@alerts_bp.route('/settings', methods=['PUT'])
@admin_required
def update_alert_settings():
    """更新预警设置（管理员）"""
    data = request.get_json()
    
    if 'alert_email' in data:
        setting = SystemSetting.query.filter_by(key='alert_email').first()
        if not setting:
            setting = SystemSetting(key='alert_email', description='库存预警邮件接收地址')
            db.session.add(setting)
        setting.value = data['alert_email']

    if 'alert_check_interval' in data:
        setting = SystemSetting.query.filter_by(key='alert_check_interval').first()
        if not setting:
            setting = SystemSetting(key='alert_check_interval', description='预警检查频率，单位分钟')
            db.session.add(setting)
        setting.value = str(data['alert_check_interval'])

    if 'alert_email_enabled' in data:
        setting = SystemSetting.query.filter_by(key='alert_email_enabled').first()
        if not setting:
            setting = SystemSetting(key='alert_email_enabled', description='库存预警邮件开关')
            db.session.add(setting)
        setting.value = str(data['alert_email_enabled']).lower()

    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '预警设置已保存',
        'data': data
    })
