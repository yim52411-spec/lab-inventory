"""后台定时任务入口。"""


def run_scheduled_tasks(app):
    from app import db
    from app.api.settings import ensure_scheduled_backup, ensure_scheduled_alert_check

    with app.app_context():
        try:
            ensure_scheduled_alert_check()
            ensure_scheduled_backup()
        except Exception:
            db.session.rollback()
            app.logger.exception('后台预警/备份任务执行失败')
