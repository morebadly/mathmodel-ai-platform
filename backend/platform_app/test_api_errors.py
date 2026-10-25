"""Error text and whole-PATCH rollback regressions using only isolated fixtures."""
import copy
import json
from types import SimpleNamespace
import uuid

from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.exceptions import APIException, AuthenticationFailed, ErrorDetail, NotFound, PermissionDenied, Throttled, ValidationError

from .api_errors import FALLBACK_MESSAGE, SERVER_ERROR_MESSAGE
from .domain import Conflict
from .models import Audit, Record, SearchChunk, User, Workspace
from .tests import Client
from .views import api_exception


class APIErrorTextTests(SimpleTestCase):
    def response(self, error, context=None):
        response = api_exception(error, context or {})
        self.assertIsNotNone(response)
        message = response.data['error']['message']
        self.assertIs(type(message), str)
        self.assertNotIn('ErrorDetail', message)
        self.assertNotIn("code='", message)
        return response

    def test_scalar_validation_is_plain_chinese(self):
        response = self.response(ValidationError('字段无效：title'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['message'], '标题无效，请检查是否已填写并符合长度要求。')

    def test_draft_context_names_the_document_title_without_reflecting_values(self):
        request = SimpleNamespace(path='/api/workspace', _full_data={'changes': {'writingDrafts': [{'title': 'do-not-reflect-fixture-content'}]}})
        response = self.response(ValidationError('字段无效：title'), {'request': request})
        self.assertEqual(response.data['error']['message'], '文稿标题无效，请检查是否已填写并符合长度要求。')
        self.assertNotIn('do-not-reflect', response.data['error']['message'])

    def test_mixed_collections_do_not_guess_the_wrong_title_type(self):
        request = SimpleNamespace(path='/api/workspace', _full_data={'changes': {'projects': [{}], 'writingDrafts': [{}]}})
        response = self.response(ValidationError('字段无效：title'), {'request': request})
        self.assertTrue(response.data['error']['message'].startswith('标题无效'))

    def test_list_errors_remain_readable_and_duplicates_collapse(self):
        response = self.response(ValidationError(['请选择文件。', '请选择文件。', '文件大小超限。']))
        self.assertEqual(response.data['error']['message'], '请选择文件。；文件大小超限。')

    def test_dictionary_keeps_each_field_hint(self):
        response = self.response(ValidationError({'title': ['不能为空。', '不能超过长度限制。'], 'body': ['正文格式无效。']}))
        self.assertEqual(response.data['error']['message'], '标题：不能为空。；标题：不能超过长度限制。；正文：正文格式无效。')

    def test_nested_containers_preserve_field_paths_and_array_indexes(self):
        response = self.response(ValidationError({'sections': [{}, {'title': [ErrorDetail('不能为空。', code='blank')]}], 'non_field_errors': ['请检查文稿。']}))
        self.assertEqual(response.data['error']['message'], 'sections[1].title：不能为空。；请检查文稿。')

    def test_detail_field_does_not_discard_other_field_errors(self):
        response = self.response(ValidationError({'detail': ['请检查输入。'], 'title': ['不能为空。']}))
        self.assertIn('detail：请检查输入。', response.data['error']['message'])
        self.assertIn('标题：不能为空。', response.data['error']['message'])

    def test_empty_errors_use_a_useful_fallback(self):
        for detail in [[], {}]:
            with self.subTest(detail=detail):
                self.assertEqual(self.response(ValidationError(detail)).data['error']['message'], FALLBACK_MESSAGE)

    def test_permissions_not_found_and_conflicts_keep_their_status_and_message(self):
        for error, status, message in [(PermissionDenied('不能修改此记录。'), 403, '不能修改此记录。'), (NotFound('记录不存在或无权访问。'), 404, '记录不存在或无权访问。'), (Conflict(), 409, Conflict.default_detail)]:
            with self.subTest(status=status):
                response = self.response(error)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.data['error']['message'], message)

    def test_retry_after_and_authenticate_headers_survive(self):
        throttled = self.response(Throttled(wait=7))
        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(throttled['Retry-After'], '7')
        error = AuthenticationFailed('请重新登录。')
        error.auth_header = 'Fixture'
        unauthorized = self.response(error)
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(unauthorized['WWW-Authenticate'], 'Fixture')

    def test_handled_server_errors_hide_internal_detail(self):
        response = self.response(APIException('SELECT private_fixture_password FROM internal_table; fixture-secret-not-for-client'))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error']['message'], SERVER_ERROR_MESSAGE)
        self.assertNotIn('SELECT', response.data['error']['message'])
        self.assertNotIn('fixture-secret', response.data['error']['message'])

    def test_unhandled_errors_are_not_swallowed_or_stringified(self):
        class PrivateFailure(Exception):
            def __str__(self):
                raise AssertionError('Internal exception text must not be read')
        self.assertIsNone(api_exception(PrivateFailure(), {}))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MAIL_TRANSPORT='local', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', AI_API_KEY='')
class WorkspaceErrorAtomicityTests(TestCase):
    client_class = Client

    def setUp(self):
        cache.clear()
        self.owner = self.person('error-owner')
        self.other = self.person('error-other')
        self.client.force_login(self.owner, backend='django.contrib.auth.backends.ModelBackend')

    def person(self, label):
        user = User.objects.create_user(label + '@example.invalid', None, display_name=label)
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        return user

    def draft(self, **extra):
        return {'id': 'draft_' + uuid.uuid4().hex, 'title': '独立测试文稿', 'content': '独立测试正文', **extra}

    def patch_workspace(self, changes, preferences=None):
        return self.client.patch('/api/workspace', json.dumps({'changes': changes, 'preferences': preferences or {}}), content_type='application/json')

    def assert_plain_failure(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertIs(type(response.json()['error']['message']), str)
        self.assertNotIn('ErrorDetail', response.content.decode())

    def test_invalid_draft_title_returns_400_with_document_field_name(self):
        invalid = self.draft(title='')
        response = self.patch_workspace({'writingDrafts': [invalid]})
        self.assert_plain_failure(response, 400)
        self.assertIn('文稿标题', response.json()['error']['message'])
        self.assertFalse(Record.objects.filter(pk=invalid['id']).exists())

    def test_later_invalid_record_rolls_back_prior_update_creation_audit_and_workspace(self):
        original = self.draft()
        existing = Record.objects.create(id=original['id'], owner=self.owner, collection='writingDrafts', payload=original, revision=4)
        updated = {**original, 'title': '应回滚的更新', '_revision': 4}
        new = self.draft()
        invalid = self.draft(title='')
        before_audits = Audit.objects.count()
        response = self.patch_workspace({'writingDrafts': [updated, new, invalid]})
        self.assert_plain_failure(response, 400)
        existing.refresh_from_db()
        self.assertEqual(existing.payload, original)
        self.assertEqual(existing.revision, 4)
        self.assertEqual(Record.objects.count(), 1)
        self.assertFalse(Record.objects.filter(pk__in=[new['id'], invalid['id']]).exists())
        self.assertEqual(Audit.objects.count(), before_audits)
        self.assertFalse(Workspace.objects.filter(user=self.owner).exists())

    def test_failure_in_later_collection_rolls_back_earlier_collection(self):
        competition = {'id': 'competition_' + uuid.uuid4().hex, 'title': '应回滚的模拟竞赛'}
        response = self.patch_workspace({'competitions': [competition], 'writingDrafts': [self.draft(title='')]})
        self.assert_plain_failure(response, 400)
        self.assertFalse(Record.objects.exists())
        self.assertFalse(Audit.objects.exists())

    def test_late_preferences_failure_rolls_back_records_audit_chunks_and_new_workspace(self):
        rid = 'resource_' + uuid.uuid4().hex
        original = {'id': rid, 'name': '独立测试资料.txt', 'text': '原检索正文', 'kind': 'knowledge', 'scope': '个人资料'}
        resource = Record.objects.create(id=rid, owner=self.owner, collection='resources', payload=original)
        chunk = SearchChunk.objects.create(resource=resource, text='原检索正文', start=0, end=6, revision=resource.revision, sha256='fixture')
        before_chunk = copy.deepcopy(chunk.__dict__)
        changes = {'resources': [{**original, 'text': '应回滚的正文', '_revision': resource.revision}], 'writingDrafts': [self.draft()]}
        response = self.patch_workspace(changes, {'weights': [1] * 7})
        self.assert_plain_failure(response, 400)
        resource.refresh_from_db()
        self.assertEqual(resource.payload, original)
        self.assertEqual(resource.revision, 1)
        self.assertEqual(Record.objects.count(), 1)
        self.assertTrue(SearchChunk.objects.filter(pk=chunk.pk, text=before_chunk['text'], revision=before_chunk['revision']).exists())
        self.assertFalse(Audit.objects.exists())
        self.assertFalse(Workspace.objects.filter(user=self.owner).exists())

    def test_stale_revision_preserves_409_and_rolls_back_prior_creation(self):
        original = self.draft()
        existing = Record.objects.create(id=original['id'], owner=self.owner, collection='writingDrafts', payload=original, revision=3)
        new = self.draft()
        response = self.patch_workspace({'writingDrafts': [new, {**original, 'title': '过期页面更新', '_revision': 2}]})
        self.assert_plain_failure(response, 409)
        self.assertFalse(Record.objects.filter(pk=new['id']).exists())
        existing.refresh_from_db()
        self.assertEqual(existing.payload, original)
        self.assertEqual(existing.revision, 3)

    def test_permission_failure_preserves_403_and_rolls_back_prior_creation(self):
        private = self.draft(title='不应显示的他人文稿')
        existing = Record.objects.create(id=private['id'], owner=self.other, collection='writingDrafts', payload=private)
        new = self.draft()
        response = self.patch_workspace({'writingDrafts': [new, {**private, 'title': '禁止修改', '_revision': existing.revision}]})
        self.assert_plain_failure(response, 403)
        self.assertFalse(Record.objects.filter(pk=new['id']).exists())
        self.assertNotIn(private['title'], response.content.decode())
        self.assertNotIn(private['id'], response.content.decode())
        existing.refresh_from_db()
        self.assertEqual(existing.payload, private)

    def test_missing_and_forbidden_files_keep_identical_404_response(self):
        row = Record.objects.create(id='private_' + uuid.uuid4().hex, owner=self.other, collection='resources', payload={'name': '不应显示的附件'})
        missing = self.client.get('/api/files/missing_fixture_record')
        forbidden = self.client.get('/api/files/' + row.id)
        self.assert_plain_failure(missing, 404)
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(missing.json(), forbidden.json())
        self.assertNotIn(row.id, forbidden.content.decode())

    def test_malformed_json_and_method_error_preserve_400_and_405(self):
        malformed = self.client.patch('/api/workspace', '{"changes":', content_type='application/json')
        self.assert_plain_failure(malformed, 400)
        method = self.client.post('/api/workspace', '{}', content_type='application/json')
        self.assert_plain_failure(method, 405)
        self.assertIn('GET', method['Allow'])
        self.assertIn('PATCH', method['Allow'])

    def test_valid_draft_still_saves_successfully(self):
        draft = self.draft()
        response = self.patch_workspace({'writingDrafts': [draft]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['versions']['writingDrafts/' + draft['id']], 1)
        self.assertEqual(Record.objects.get(pk=draft['id']).payload, draft)
