"""为已有数据库补充批次库存和批次预警字段。

执行方式：在 backend 目录运行 `python3 migrate_product_shelf_life.py`。
脚本只新增表和可空字段，不删除或覆盖业务数据。
"""
from sqlalchemy import inspect, text

from app import create_app, db


app = create_app('development')


with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'material_batches' not in tables:
        db.create_all()
    alert_columns = {column['name'] for column in inspect(db.engine).get_columns('alerts')}
    if 'batch_id' not in alert_columns:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE alerts ADD COLUMN batch_id INTEGER'))
    print('批次库存结构迁移完成；未删除或覆盖已有数据。')
