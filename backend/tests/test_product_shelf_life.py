import os
import sys
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask_jwt_extended import create_access_token
from app import create_app, db
from app.models import Alert, Category, Material, MaterialBatch, OperationRecord, User
from app.api.alerts import sync_batch_expiry_alert


class ProductShelfLifeTestCase(unittest.TestCase):
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

    def test_stock_in_creates_batch_and_expiry_alert(self):
        response = self.client.post('/api/inventory/in', headers=self.headers, json={
            'material_id': self.material_id,
            'quantity': 5,
            'batch_no': 'REAL-BATCH-1',
            'production_date': '2026-01-01',
            'expiry_date': (date.today() + timedelta(days=10)).isoformat(),
            'related_type': 'other'
        })
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            batch = MaterialBatch.query.one()
            self.assertEqual(batch.batch_no, 'REAL-BATCH-1')
            self.assertEqual(batch.quantity_remaining, 5)
            self.assertEqual(Alert.query.filter_by(alert_type='expiry', batch_id=batch.id).count(), 1)

    def test_stock_in_allows_blank_batch_dates_and_normalizes_date_formats(self):
        for index, date_value in enumerate(('2026-08-08', '2026/8/8', '20260808', '2026-8-8', '2026/08/08', '9/9', '9-9', '2026-9/9')):
            response = self.client.post('/api/inventory/in', headers=self.headers, json={
                'material_id': self.material_id,
                'quantity': 1,
                'batch_no': 'DATE-%s' % index,
                'production_date': date_value,
                'expiry_date': None,
                'shelf_life_days': None,
            })
            self.assertEqual(response.status_code, 200, response.get_json())

        response = self.client.post('/api/inventory/in', headers=self.headers, json={
            'material_id': self.material_id,
            'quantity': 1,
            'batch_no': 'BLANK',
            'production_date': '   ',
            'expiry_date': '   ',
            'shelf_life_days': '   ',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            blank = MaterialBatch.query.filter_by(batch_no='BLANK').one()
            self.assertIsNone(blank.production_date)
            self.assertIsNone(blank.expiry_date)

    def test_stock_in_allows_all_batch_fields_blank(self):
        response = self.client.post('/api/inventory/in', headers=self.headers, json={
            'material_id': self.material_id,
            'quantity': 1,
            'batch_no': '   ',
            'production_date': '   ',
            'expiry_date': '   ',
            'shelf_life_days': '   '
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()['success'])

    def test_out_consumes_older_batch_first(self):
        with self.app.app_context():
            material = db.session.get(Material, self.material_id)
            material.stock = 8
            older = MaterialBatch(material=material, batch_no='OLD', received_at=datetime(2026, 1, 1),
                                  expiry_date=date(2026, 12, 1), quantity_received=3, quantity_remaining=3)
            newer = MaterialBatch(material=material, batch_no='NEW', received_at=datetime(2026, 2, 1),
                                  expiry_date=date(2027, 12, 1), quantity_received=5, quantity_remaining=5)
            db.session.add_all([older, newer])
            db.session.commit()
        response = self.client.post('/api/inventory/out', headers=self.headers, json={
            'material_id': self.material_id, 'quantity': 4
        })
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(MaterialBatch.query.filter_by(batch_no='OLD').one().quantity_remaining, 0)
            self.assertEqual(MaterialBatch.query.filter_by(batch_no='NEW').one().quantity_remaining, 4)

    def test_history_keyword_search(self):
        with self.app.app_context():
            db.session.add(OperationRecord(operation_no='I-1', type='in', user_id=self.user_id,
                                           material_id=self.material_id, material_name='目标试剂', quantity=1))
            db.session.commit()
        response = self.client.get('/api/records?type=inventory&keyword=目标试剂', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()['data']['items']), 1)

    def test_history_pagination_reports_real_count(self):
        with self.app.app_context():
            for index in range(2):
                db.session.add(OperationRecord(
                    operation_no='I-%s' % index, type='in', user_id=self.user_id,
                    material_id=self.material_id, material_name='物料%s' % index,
                    quantity=1
                ))
            db.session.commit()
        response = self.client.get('/api/records?type=inventory&page=1&per_page=1', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['pages'], 2)
        self.assertEqual(len(data['items']), 1)

    def test_mail_status_does_not_expose_password(self):
        response = self.client.get('/api/alerts/mail-status', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertIn('configured', data)
        self.assertNotIn('password', data)

    def test_scheduled_task_accepts_application_context(self):
        from app.api.scheduler import run_scheduled_tasks
        with patch('app.api.settings.ensure_scheduled_alert_check') as check, \
                patch('app.api.settings.ensure_scheduled_backup') as backup:
            run_scheduled_tasks(self.app)
        check.assert_called_once_with()
        backup.assert_called_once_with()

    def test_monthly_purchase_trend_is_returned(self):
        with self.app.app_context():
            from app.models import PurchaseRequest
            db.session.add(PurchaseRequest(request_no='P-1', user_id=self.user_id, material_name='试剂',
                                           quantity=2, estimated_price=10, reason='补充',
                                           created_at=datetime(2026, 1, 10)))
            db.session.add(PurchaseRequest(request_no='P-2', user_id=self.user_id, material_name='试剂',
                                           quantity=3, estimated_price=20, reason='补充',
                                           created_at=datetime(2026, 1, 20)))
            db.session.commit()
        response = self.client.get('/api/records/dashboard', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        trend = response.get_json()['data']['purchase_trend']
        self.assertEqual(trend[-1], {'month': '2026-01', 'quantity': 5, 'amount': 80.0})

    def test_mail_failure_does_not_mark_alert_sent(self):
        with self.app.app_context():
            material = db.session.get(Material, self.material_id)
            batch = MaterialBatch(material=material, batch_no='MAIL', received_at=datetime.utcnow(),
                                  expiry_date=date.today(), quantity_received=1, quantity_remaining=1)
            db.session.add(batch)
            db.session.flush()
            sync_batch_expiry_alert(batch)
            db.session.commit()
            self.app.config.update(MAIL_SERVER='smtp.test', MAIL_USERNAME='u', MAIL_PASSWORD='p',
                                   MAIL_DEFAULT_SENDER='u@test', ALERT_EMAIL_ENABLED=True)
            from app.api.alerts import send_pending_alert_emails
            with patch('app.api.alerts.mail.send', side_effect=RuntimeError('smtp down')):
                self.assertEqual(send_pending_alert_emails(), 0)
            self.assertFalse(Alert.query.one().is_sent)


if __name__ == '__main__':
    unittest.main()
