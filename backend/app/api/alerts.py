"""
库存预警API
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import and_
from datetime import datetime, timedelta
from app import db, mail
from app.models import Alert, Material, User, SystemSetting
from app.api.auth import admin_required
from flask_mail import Message

alerts_bp = Blueprint('alerts', __name__)


def sync_material_alert(material):
    """Keep unresolved stock alerts aligned with the material's current stock."""
    unresolved = Alert.query.filter_by(material_id=material.id, is_resolved=False).all()

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

    materials = Material.query.all()

    for material in materials:
        had_unresolved = Alert.query.filter(
            and_(Alert.material_id == material.id, Alert.is_resolved == False)
        ).first()
        alert = sync_material_alert(material)
        if alert and not had_unresolved:
            new_alerts.append(alert)
    
    db.session.commit()

    email_status = 'disabled'
    if get_setting('alert_email_enabled', 'true') == 'true' and new_alerts:
        if mail_is_configured():
            response = send_alert_emails()
            send_result = response[0].get_json() if isinstance(response, tuple) else response.get_json()
            email_status = send_result.get('message', '邮件发送已触发')
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
    
    sent_count = 0
    
    try:
        # 构建邮件内容
        subject = f'【库存预警】{len(unsent_alerts)} 条物料库存预警通知'
        
        body = '<h2>库存预警通知</h2>'
        body += '<p>以下物料库存不足，请及时处理：</p>'
        body += '<table border="1" cellpadding="10">'
        body += '<tr><th>物料编号</th><th>物料名称</th><th>当前库存</th><th>预警阈值</th><th>级别</th></tr>'
        
        for alert in unsent_alerts:
            material = alert.material
            color = '#ef4444' if alert.level == 'danger' else '#f59e0b'
            level_text = '严重不足' if alert.level == 'danger' else '库存预警'
            
            body += f'<tr>'
            body += f'<td>{material.code}</td>'
            body += f'<td>{material.name}</td>'
            body += f'<td>{alert.current_stock}</td>'
            body += f'<td>{alert.threshold}</td>'
            body += f'<td style="color: {color}">{level_text}</td>'
            body += f'</tr>'
            
            # 标记为已发送
            alert.is_sent = True
            alert.sent_at = datetime.utcnow()
        
        body += '</table>'
        body += '<p>请登录系统查看详情并及时采购补充库存。</p>'
        
        # 发送邮件
        msg = Message(
            subject=subject,
            recipients=admin_emails,
            html=body
        )
        mail.send(msg)
        
        db.session.commit()
        sent_count = len(unsent_alerts)
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'邮件发送失败: {str(e)}'
        }), 500
    
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
