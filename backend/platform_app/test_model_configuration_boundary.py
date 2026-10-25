"""Model configuration stays server-owned; fixtures never call a model service."""
import json
from unittest.mock import patch
from urllib.parse import urlsplit

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings

from .access import ADMIN_EMAILS, ADMIN_LOGINS
from .models import AIRun, User, Workspace
from .tests import Client, person


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    AI_BASE_URL='https://private-model-boundary.example.invalid/provider-v1',
    AI_MODEL='platform-model-boundary-fixture',
    AI_API_KEY='isolated-model-key-boundary-never-use',
    SITE_URL='http://testserver',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MAIL_TRANSPORT='local',
    ALLOW_DEV_MAILBOX=False,
    E2B_API_KEY='',
    RUNNER_URL='',
    RUNNER_API_KEY='',
)
class ModelConfigurationBoundaryTests(TestCase):
    client_class = Client

    @classmethod
    def setUpTestData(cls):
        cls.student = person('model-boundary-student')
        cls.mentor = person('model-boundary-mentor', 'mentor')
        cls.admins = [
            User.objects.create_superuser(ADMIN_EMAILS[alias], None)
            for alias in ADMIN_LOGINS
        ]
        cls.unlisted_admin = User.objects.create_user(
            'model-boundary-unlisted@example.invalid', None,
            role='admin', is_staff=True, is_superuser=True,
        )
        EmailAddress.objects.create(
            user=cls.unlisted_admin, email=cls.unlisted_admin.email,
            primary=True, verified=True,
        )

    def setUp(self):
        cache.clear()
        # Any accidental provider call fails immediately instead of reaching a network.
        gateway = patch('platform_app.views.httpx.Client', side_effect=AssertionError(
            'Configuration boundary tests must not call a model provider.'
        ))
        self.gateway = gateway.start()
        self.addCleanup(gateway.stop)

    def tearDown(self):
        self.gateway.assert_not_called()
        self.assertFalse(AIRun.objects.exists())

    def client_for(self, user=None):
        client = Client()
        if user is not None:
            client.force_login(user, backend='django.contrib.auth.backends.ModelBackend')
        return client

    def assert_provider_details_absent(self, response):
        body = response.content.decode('utf-8')
        self.assertNotIn(settings.AI_BASE_URL, body)
        self.assertNotIn(urlsplit(settings.AI_BASE_URL).hostname, body)
        self.assertNotIn(settings.AI_API_KEY, body)

    def test_all_three_fixed_administrators_can_read_readiness(self):
        for admin in self.admins:
            with self.subTest(account=admin.admin_login):
                response = self.client_for(admin).get('/api/admin/readiness')
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.json()['aiConfigured'], True)
                self.assert_provider_details_absent(response)

    def test_readiness_denies_anonymous_and_nonadministrative_identities(self):
        for user in [None, self.student, self.mentor, self.unlisted_admin]:
            with self.subTest(account=user.email if user else 'anonymous'):
                response = self.client_for(user).get('/api/admin/readiness')
                self.assertEqual(response.status_code, 403)
                self.assert_provider_details_absent(response)

    def test_public_capabilities_never_expose_provider_address_or_key(self):
        for user in [None, self.student, self.mentor, *self.admins]:
            with self.subTest(account=user.email if user else 'anonymous'):
                response = self.client_for(user).get('/api/capabilities')
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.json()['ai'], True)
                self.assertEqual(response.json()['model'], settings.AI_MODEL)
                self.assert_provider_details_absent(response)

    def test_workspace_exposes_platform_gateway_instead_of_provider_details(self):
        for user in [self.student, self.mentor, *self.admins]:
            with self.subTest(account=user.email):
                response = self.client_for(user).get('/api/workspace')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()['settings']['endpoint'], settings.SITE_URL + '/api/ai',
                )
                self.assertEqual(response.json()['settings']['model'], settings.AI_MODEL)
                self.assert_provider_details_absent(response)

    def test_students_and_mentors_cannot_persist_forged_model_configuration(self):
        forged = {
            'provider': 'ollama',
            'endpoint': 'https://attacker-model-boundary.example.invalid',
            'model': 'attacker-model-boundary',
            'key': 'attacker-key-boundary',
        }
        authoritative = (settings.AI_BASE_URL, settings.AI_MODEL, settings.AI_API_KEY)
        weights = [30, 10, 20, 10, 10, 10, 10]
        for user in [self.student, self.mentor]:
            with self.subTest(account=user.email):
                client = self.client_for(user)
                response = client.patch('/api/workspace', json.dumps({
                    **forged,
                    'settings': forged,
                    'changes': {},
                    'preferences': {**forged, 'settings': forged, 'weights': weights},
                }), content_type='application/json')
                self.assertEqual(response.status_code, 200)

                preferences = Workspace.objects.get(user=user).preferences
                self.assertEqual(preferences['weights'], weights)
                stored = json.dumps(preferences)
                for value in forged.values():
                    self.assertNotIn(value, stored)
                self.assertEqual(
                    (settings.AI_BASE_URL, settings.AI_MODEL, settings.AI_API_KEY),
                    authoritative,
                )

                reloaded = client.get('/api/workspace')
                self.assertEqual(reloaded.status_code, 200)
                self.assertEqual(
                    reloaded.json()['settings']['endpoint'], settings.SITE_URL + '/api/ai',
                )
                self.assertEqual(reloaded.json()['settings']['model'], settings.AI_MODEL)
                self.assert_provider_details_absent(reloaded)
