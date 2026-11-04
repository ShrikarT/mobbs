import unittest
from unittest.mock import patch
import psycopg
from fastapi.testclient import TestClient
from apps.api.app.main import app
from apps.api.app.config import settings


class DatabaseOutageTests(unittest.TestCase):
    def test_outage_returns_safe_service_unavailable_without_private_details(self):
        with patch('apps.api.app.main.connection',side_effect=psycopg.OperationalError('private connection details')):
            response=TestClient(app,base_url=settings().origin).get('/health')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['code'],'database_temporarily_unavailable')
        self.assertNotIn('private connection',response.text)
        self.assertEqual(response.headers['Retry-After'],'3')
