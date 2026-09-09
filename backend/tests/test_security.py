import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models import Alert, BorrowRecord, Category, Material, PurchaseRequest, User


class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.first_user = self.add_user('first')
            self.second_user = self.add_user('second')
            self.admin_user = self.add_user('admin', role='admin')
            self.admin_user_id = self.admin_user.id
            self.first_user_id = self.first_user.id
            self.second_user_id = self.second_user.id
            db.session.add(PurchaseRequest(
                request_no='P-TEST-1', user_id=self.second_user.id,
                material_name='test', quantity=1, reason='test'
            ))
            db.session.add(BorrowRecord(
                borrow_no='B-TEST-1', user_id=self.second_user.id,
                material_id=1, quantity=1, expected_return_date=datetime(2099, 12, 31)
            ))
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def add_user(self, username, role='visitor'):
        user = User(username=username, name=username, role=role, is_active=True)
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        return user

    def headers_for(self, user_id, role='visitor'):
        with self.app.app_context():
            token = create_access_token(identity=str(user_id), additional_claims={'role': role})
        return {'Authorization': f'Bearer {token}'}

    def test_user_cannot_read_another_users_records(self):
        headers = self.headers_for(self.first_user_id)
        self.assertEqual(self.client.get('/api/purchase/1', headers=headers).status_code, 403)
        self.assertEqual(self.client.get('/api/borrow/1', headers=headers).status_code, 403)

    def test_logout_revokes_access_token(self):
        headers = self.headers_for(self.first_user_id)
        self.assertEqual(self.client.post('/api/auth/logout', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/materials', headers=headers).status_code, 401)

    def test_excel_import_merges_and_allows_incomplete_materials(self):
        with self.app.app_context():
            category = Category(name='耗材', code='test-consumable')
            material = Material(code='M-1', name='移液器', category=category, stock=8, unit='个', threshold=3)
            db.session.add_all([category, material])
            db.session.commit()

        headers = self.headers_for(self.admin_user_id, 'admin')
        response = self.client.post('/api/materials/import', headers=headers, json={'items': [
            {'name': '移液器 1000ul', 'stock': 2, 'purchase_date': '2025.10.15'},
            {'name': '未知物品', 'stock': 3, 'purchase_date': '2025.10.16'},
            {'name': '', 'stock': 1, 'purchase_date': '2025.10.17'},
            {'name': '无数量物品', 'stock': 0},
            {'物品名称': '胶带', '分类': '通用运维/辅料类', '数量': 10, '预设阀值': 4, '地区': '南昌'}
        ]})
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(Material.query.filter_by(code='M-1').one().stock, 10)
            self.assertEqual(Material.query.filter(Material.code.like('TEMP-%')).count(), 3)
            tape = Material.query.filter_by(name='胶带').one()
            self.assertEqual((tape.stock, tape.threshold, tape.location), (10, 4, '南昌'))

    def test_delete_material_with_alert_returns_validation_error(self):
        with self.app.app_context():
            category = Category(name='试剂', code='test-chemical')
            material = Material(code='M-DELETE', name='不可删除物料', category=category, stock=0, threshold=1)
            db.session.add_all([category, material])
            db.session.flush()
            db.session.add(Alert(material_id=material.id, alert_type='stock_low', level='danger'))
            db.session.commit()

        headers = self.headers_for(self.admin_user_id, 'admin')
        response = self.client.delete('/api/materials/1', headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn('库存预警1条', response.get_json()['message'])


if __name__ == '__main__':
    unittest.main()
