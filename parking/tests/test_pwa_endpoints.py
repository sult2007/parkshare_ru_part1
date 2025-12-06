import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backend.settings.local")

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class PushSubscriptionAPITest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        django.setup()
        settings.ALLOWED_HOSTS.append("testserver")

    def setUp(self):
        self.client = APIClient()

    def test_requires_payload(self):
        url = reverse('push-subscription-list')
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_authenticated_create(self):
        User = get_user_model()
        user = User.objects.create_user(username='pwa-user', password='pw')
        self.client.force_authenticate(user)
        url = reverse('push-subscription-list')
        payload = {
            'endpoint': 'https://example.com/sub',
            'p256dh': 'key',
            'auth': 'auth',
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['endpoint'], payload['endpoint'])
