"""到期提醒功能增强测试：Excel导入批次、新增物料首批效期、报废原因备注"""
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask_jwt_extended import create_access_token
from app import create_app, db
from app.models import Alert, Category, Material, MaterialBatch, OperationRecord, User


class ExpiryEnhancementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username='admin', name='管理员', role='admin', is_active=True)
            user.set_password('password')
            category = Category(name='耗材', code='test')
            material = Material(code='M-TEST', name='试剂', spec='同规格', category=category, stock=0)
            db.session.add_all([user, category, material])
            db.session.commit()
            self.user_id = user.id
            self.material_id = material.id
        with self.app.app_context():
            token = create_access_token(identity=str(self.user_id), additional_claims={'role': 'admin'})
        self.headers = {'Authorization': f'Bearer {token}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # ---------- 改动1：Excel 导入批次支持 ----------

    def test_import_with_expiry_creates_batch(self):
        """导入新物料行含有效期 → 创建批次并纳入到期预警"""
        expiry = (date.today() + timedelta(days=20)).isoformat()
        response = self.client.post('/api/materials/import', headers=self.headers, json={
            'items': [{'code': 'IMP-1', 'name': '离心管套装', 'stock': 8, 'expiry_date': expiry,
                       'category_name': '耗材', 'production_date': '2026-01-01'}]
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            material = Material.query.filter_by(code='IMP-1').one()
            batch = MaterialBatch.query.filter_by(material_id=material.id).one()
            self.assertEqual(batch.quantity_remaining, 8)
            self.assertEqual(batch.expiry_date.isoformat(), expiry)
            self.assertEqual(Alert.query.filter_by(alert_type='expiry', batch_id=batch.id).count(), 1)

    def test_import_without_expiry_skips_batch(self):
        """导入行无有效期/保质期/批次号 → 不建批次，物料正常导入"""
        response = self.client.post('/api/materials/import', headers=self.headers, json={
            'items': [{'code': 'IMP-2', 'name': '普通耗材B', 'stock': 5, 'category_name': '耗材'}]
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIn('成功处理 1 条', response.get_json()['message'])
        with self.app.app_context():
            material = Material.query.filter_by(code='IMP-2').one()
            self.assertEqual(material.stock, 5)
            self.assertEqual(MaterialBatch.query.filter_by(material_id=material.id).count(), 0)

    def test_import_merge_existing_material_creates_batch(self):
        """导入匹配已有物料（名称精确匹配）→ 批次同样创建"""
        expiry = (date.today() + timedelta(days=15)).isoformat()
        response = self.client.post('/api/materials/import', headers=self.headers, json={
            'items': [{'name': '试剂', 'stock': 6, 'batch_no': 'IMP-BT-1', 'expiry_date': expiry}]
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            material = Material.query.get(self.material_id)
            self.assertEqual(material.stock, 6)
            batch = MaterialBatch.query.filter_by(batch_no='IMP-BT-1').one()
            self.assertEqual(batch.quantity_remaining, 6)

    def test_import_shelf_life_days_derives_expiry(self):
        """导入行只有生产日期+保质期天数 → 用入库日+保质期推算有效期"""
        response = self.client.post('/api/materials/import', headers=self.headers, json={
            'items': [{'code': 'IMP-3', 'name': '推算效期C', 'stock': 3, 'shelf_life_days': 365,
                       'category_name': '耗材'}]
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            batch = MaterialBatch.query.filter_by(
                material_id=Material.query.filter_by(code='IMP-3').one().id).one()
            self.assertIsNotNone(batch.expiry_date)
            self.assertEqual(batch.shelf_life_days, 365)

    # ---------- 改动2：新增物料首批效期 ----------

    def test_create_material_with_initial_batch(self):
        """新增物料带首批效期 → 物料+批次+入库记录三表一致"""
        expiry = (date.today() + timedelta(days=30)).isoformat()
        response = self.client.post('/api/materials', headers=self.headers, json={
            'code': 'NEW-1', 'name': '首批物料', 'stock': 10, 'threshold': 5, 'category_id': None,
            'initial_batch': {'batch_no': 'NEW-BT-1', 'production_date': '2026-01-01',
                              'expiry_date': expiry}
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertIn('首批批次已创建', response.get_json()['message'])
        with self.app.app_context():
            material = Material.query.filter_by(code='NEW-1').one()
            batch = MaterialBatch.query.filter_by(material_id=material.id).one()
            self.assertEqual(batch.quantity_remaining, 10)
            self.assertEqual(batch.expiry_date.isoformat(), expiry)
            record = OperationRecord.query.filter_by(material_id=material.id, type='in').one()
            self.assertEqual(record.remark, '新增物料首批入库')

    def test_create_material_without_initial_batch_unchanged(self):
        """新增物料不带首批效期 → 行为与现状一致（无批次）"""
        response = self.client.post('/api/materials', headers=self.headers, json={
            'code': 'NEW-2', 'name': '普通物料', 'stock': 2, 'threshold': 5
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        with self.app.app_context():
            material = Material.query.filter_by(code='NEW-2').one()
            self.assertEqual(MaterialBatch.query.filter_by(material_id=material.id).count(), 0)

    # ---------- 改动3：报废原因备注 ----------

    def _create_expiry_alert(self):
        """入库即将到期批次，返回预警 id"""
        expiry = (date.today() + timedelta(days=5)).isoformat()
        self.client.post('/api/inventory/in', headers=self.headers, json={
            'material_id': self.material_id, 'quantity': 4, 'batch_no': 'SCRAP-BT-1',
            'expiry_date': expiry
        })
        with self.app.app_context():
            return Alert.query.filter_by(alert_type='expiry').one().id

    def test_resolve_with_reason_and_handling(self):
        """报废携带原因/处理方式/备注 → 出库记录 remark 完整体现"""
        alert_id = self._create_expiry_alert()
        response = self.client.post(f'/api/alerts/{alert_id}/resolve', headers=self.headers, json={
            'reason': '变质', 'handling': '退回供应商', 'remark': '送检不合格'
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            record = OperationRecord.query.filter_by(type='scrap').one()
            self.assertIn('原因: 变质', record.remark)
            self.assertIn('处理: 退回供应商', record.remark)
            self.assertIn('备注: 送检不合格', record.remark)
            self.assertIn('批次SCRAP-BT-1', record.remark)
            material = Material.query.get(self.material_id)
            self.assertEqual(material.stock, 0)

    def test_resolve_without_body_keeps_default_remark(self):
        """不传 body → remark 与现状一致（向后兼容）"""
        alert_id = self._create_expiry_alert()
        response = self.client.post(f'/api/alerts/{alert_id}/resolve', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            record = OperationRecord.query.filter_by(type='scrap').one()
            self.assertEqual(record.remark, '过期报废: 批次SCRAP-BT-1')


if __name__ == '__main__':
    unittest.main()
