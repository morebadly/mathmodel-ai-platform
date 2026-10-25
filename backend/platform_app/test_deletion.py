"""Document trash regressions. Fixtures never touch a deployed user or file."""
import copy
import json
import tempfile
import uuid
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from .domain import can_read, editable, get_record, reference, save_workspace, Conflict
from .models import Asset, Audit, ChatMessage, ChatParticipant, ChatRoom, Membership, Record, SearchChunk, MailJob
from .tests import Client, person, project, record


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MAIL_TRANSPORT='local', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', AI_API_KEY='')
class DocumentTrashTests(TestCase):
    client_class = Client

    def setUp(self):
        cache.clear()
        self.temp = tempfile.TemporaryDirectory(prefix='document-trash-fixture-', dir=settings.DATA_DIR)
        self.media = override_settings(MEDIA_ROOT=self.temp.name)
        self.media.enable()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.media.disable)
        self.owner = person('trash-owner')
        self.other = person('trash-other')
        self.mentor = person('trash-mentor', 'mentor')
        self.admin = person('trash-admin', 'admin')
        self.client.force_login(self.owner, backend='django.contrib.auth.backends.ModelBackend')

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def remove(self, row, revision=None):
        return self.post(f'/api/records/{row.collection}/{row.id}/delete', {'revision': row.revision if revision is None else revision})

    def restore(self, row, revision=None):
        return self.post(f'/api/records/{row.collection}/{row.id}/restore', {'revision': row.revision if revision is None else revision})

    def detach(self, row, file_id, revision=None):
        return self.post(f'/api/records/{row.collection}/{row.id}/detach-file', {'fileId': file_id, 'revision': row.revision if revision is None else revision})

    def draft(self, owner=None):
        return record(owner or self.owner, 'writingDrafts', title='隔离测试文稿', source='保留中文正文', target='Retained English', notes='保留修改记录')

    def resource(self, owner=None, scope='个人资料', **extra):
        row = record(owner or self.owner, 'resources', name='fixture.txt', kind='knowledge', scope=scope, text='可检索的独立样例', **extra)
        row.scope = 'public' if scope == '公共知识库' else 'private'
        row.save()
        asset = Asset.objects.create(record=row, file=SimpleUploadedFile('fixture.txt', b'isolated fixture original'), original_name='fixture.txt', size=25, sha256='fixture', content_type='text/plain', parse_status='ready')
        return row, asset

    def started_competition(self):
        """The real browser's two saves: ready competition, then paired project."""
        competition_id, project_id = 'competition_' + uuid.uuid4().hex, 'project_' + uuid.uuid4().hex
        initial = {'id': competition_id, 'title': '正常开始的模拟竞赛', 'members': '甲：建模\n乙：写作', 'status': 'ready', 'hours': 6}
        first = self.client.patch('/api/workspace', json.dumps({'changes': {'competitions': [initial]}}), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        payload = {'id': project_id, 'title': initial['title'], 'competitionId': competition_id, 'resourceIds': [],
                   'stages': [{'title': str(i), 'content': '保留阶段正文' + str(i), 'done': False} for i in range(8)]}
        start = {**initial, 'projectId': project_id, 'status': 'active', '_revision': 1}
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'projects': [payload], 'competitions': [start]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return Record.objects.get(pk=competition_id), Record.objects.get(pk=project_id)

    def test_delete_draft_is_persisted_recoverable_and_hidden_from_all_normal_readers(self):
        row = self.draft()
        original = copy.deepcopy(row.payload)
        response = self.remove(row)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['revision'], 2)
        row.refresh_from_db()
        self.assertEqual(row.scope, 'deleted')
        self.assertEqual(row.payload['source'], original['source'])
        self.assertFalse(can_read(self.owner, row))
        self.assertFalse(can_read(self.admin, row))
        self.assertFalse(editable(self.owner, row))
        self.assertNotIn(row.id, [r['id'] for r in self.client.get('/api/workspace').json()['writingDrafts']])
        trash = self.client.get('/api/records/trash').json()['records']
        self.assertEqual(trash, [{'id': row.id, 'collection': 'writingDrafts', 'title': row.payload['title'], 'deletedAt': row.payload['_deletedAt'], 'revision': 2}])
        self.assertNotIn('source', trash[0])
        restored = self.restore(row)
        self.assertEqual(restored.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.scope, 'private')
        self.assertEqual(row.payload['source'], original['source'])
        self.assertNotIn('_deletedBy', row.payload)
        self.assertEqual(row.revision, 3)
        self.assertTrue(can_read(self.owner, row))
        self.assertTrue(Audit.objects.filter(action='trash:writingDrafts', target=row.id).exists())
        self.assertTrue(Audit.objects.filter(action='restore:writingDrafts', target=row.id).exists())

    def test_repeat_delete_and_restore_are_idempotent_without_extra_audits(self):
        row = self.draft()
        self.assertEqual(self.remove(row).status_code, 200)
        duplicate = self.remove(row)
        self.assertTrue(duplicate.json()['duplicate'])
        self.assertEqual(Audit.objects.filter(action='trash:writingDrafts').count(), 1)
        row.refresh_from_db()
        self.assertEqual(self.restore(row).status_code, 200)
        self.assertTrue(self.restore(row).json()['duplicate'])
        self.assertEqual(Audit.objects.filter(action='restore:writingDrafts').count(), 1)

    def test_revision_mismatch_does_not_delete_or_restore(self):
        row = self.draft()
        row.revision = 4
        row.save()
        self.assertEqual(self.remove(row, 3).status_code, 409)
        row.refresh_from_db()
        self.assertEqual(row.scope, 'private')
        self.assertEqual(self.remove(row).status_code, 200)
        row.refresh_from_db()
        self.assertEqual(self.restore(row, 4).status_code, 409)
        row.refresh_from_db()
        self.assertEqual(row.scope, 'deleted')

    def test_invalid_revision_and_unsupported_collection_are_rejected(self):
        row = self.draft()
        for revision in [None, True, 0, -1, '1', 1.0]:
            self.assertEqual(self.remove(row, revision if revision is not None else False).status_code, 400)
        self.assertEqual(self.post('/api/records/teams/unused_id/delete', {'revision': 1}).status_code, 404)

    def test_missing_and_another_users_private_document_have_identical_error(self):
        row = self.draft(self.other)
        missing = self.post('/api/records/writingDrafts/missing_fixture_document/delete', {'revision': 1})
        forbidden = self.remove(row)
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(missing.json(), forbidden.json())
        self.assertNotIn(row.payload['title'], forbidden.content.decode())
        self.assertEqual(self.restore(row).status_code, 404)
        self.assertEqual(self.client.get('/api/records/trash').json()['records'], [])

    def test_admin_maintains_public_knowledge_but_not_other_private_trash(self):
        shared, asset = self.resource(self.admin, '公共知识库')
        private = self.draft(self.other)
        self.client.force_login(self.admin, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.remove(shared).status_code, 200)
        self.assertEqual(self.remove(private).status_code, 404)
        self.assertEqual([r['id'] for r in self.client.get('/api/records/trash').json()['records']], [shared.id])
        self.client.force_login(self.other, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.remove(private).status_code, 200)
        self.client.force_login(self.admin, backend='django.contrib.auth.backends.ModelBackend')
        self.assertNotIn(private.id, [r['id'] for r in self.client.get('/api/records/trash').json()['records']])

    def test_another_fixed_admin_can_restore_public_knowledge(self):
        shared, _ = self.resource(self.admin, '公共知识库')
        self.client.force_login(self.admin, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.remove(shared).status_code, 200)
        from .access import ADMIN_EMAILS
        admin2 = type(self.admin).objects.create_user(ADMIN_EMAILS['admin02'], None, role='admin', admin_login='admin02', is_staff=True, is_superuser=True)
        self.client.force_login(admin2, backend='django.contrib.auth.backends.ModelBackend')
        shared.refresh_from_db()
        self.assertEqual(self.restore(shared).status_code, 200)
        shared.refresh_from_db()
        self.assertEqual(shared.scope, 'public')
        self.assertTrue(can_read(self.other, shared))

    def test_stale_workspace_save_cannot_resurrect_deleted_document(self):
        row = self.draft()
        stale = {**row.payload, '_revision': row.revision}
        self.assertEqual(self.remove(row).status_code, 200)
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'writingDrafts': [stale]}}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        row.refresh_from_db()
        self.assertEqual(row.scope, 'deleted')
        self.assertEqual(row.revision, 2)

    def test_resource_deletion_retains_original_clears_search_and_revokes_download(self):
        row, asset = self.resource()
        path = asset.file.path
        original = asset.file.read()
        asset.file.close()
        SearchChunk.objects.create(resource=row, revision=1, start=0, end=3, text='可检索', sha256='fixture')
        self.assertEqual(self.remove(row).status_code, 200)
        self.assertFalse(SearchChunk.objects.filter(resource=row).exists())
        from pathlib import Path
        self.assertEqual(Path(path).read_bytes(), original)
        self.assertEqual(self.client.get('/api/files/' + row.id).status_code, 404)
        self.assertEqual(self.client.get('/api/files/' + row.id + '/parse').status_code, 404)
        self.assertNotIn(row.id, [r['resourceId'] for r in self.client.get('/api/retrieval/search?q=可检索').json()['hits']])
        row.refresh_from_db()
        self.assertEqual(self.restore(row).status_code, 200)
        response = self.client.get('/api/files/' + row.id)
        self.assertEqual(response.status_code, 200)
        # Consume the real download through ClientHandler's closing wrapper.
        # Closing the response directly sends request_finished outside that
        # wrapper and can close PostgreSQL's enclosing TestCase transaction.
        self.assertEqual(b''.join(response.streaming_content), original)
        self.assertIn(row.id, [r['resourceId'] for r in self.client.get('/api/retrieval/search?q=可检索').json()['hits']])

    def test_running_parse_is_cancelled_and_restore_requeues_it(self):
        row, asset = self.resource()
        asset.parse_status = 'processing'
        asset.claimed_at = timezone.now()
        asset.save()
        self.assertEqual(self.remove(row).status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.parse_status, 'cancelled')
        self.assertIsNone(asset.claimed_at)
        row.refresh_from_db()
        self.assertEqual(self.restore(row).status_code, 200)
        asset.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual(asset.parse_status, 'pending')
        self.assertEqual(row.payload['parseStatus'], 'pending')

    def test_restore_does_not_restart_a_previously_user_cancelled_parse(self):
        row, asset = self.resource()
        asset.parse_status = 'cancelled'
        asset.save()
        self.assertEqual(self.remove(row).status_code, 200)
        row.refresh_from_db()
        self.assertEqual(self.restore(row).status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.parse_status, 'cancelled')

    def test_referenced_file_and_submitted_project_cannot_be_deleted(self):
        row, _ = self.resource()
        task = record(self.owner, 'tasks', title='独立练习', attachmentIds=[])
        current = project(self.owner, task)
        current.payload['resourceIds'] = [row.id]
        current.save()
        self.assertEqual(self.remove(row).status_code, 409)
        submission = record(self.owner, 'taskSubmissions', projectId=current.id, taskId=task.id, snapshot=copy.deepcopy(current.payload))
        self.assertEqual(self.remove(current).status_code, 409)
        self.assertNotIn(submission.id, self.remove(current).content.decode())
        self.assertEqual(Record.objects.get(pk=current.pk).scope, 'private')

    def test_paper_must_restore_after_its_original_file(self):
        resource, _ = self.resource()
        paper = record(self.owner, 'papers', title='独立论文', fileId=resource.id, projectId='', scores=[None] * 7)
        self.assertEqual(self.remove(resource).status_code, 409)
        self.assertEqual(self.remove(paper).status_code, 200)
        self.assertEqual(self.remove(resource).status_code, 200)
        paper.refresh_from_db()
        self.assertEqual(self.restore(paper).status_code, 409)
        resource.refresh_from_db()
        self.assertEqual(self.restore(resource).status_code, 200)
        self.assertEqual(self.restore(paper).status_code, 200)

    def test_shared_library_source_mapping_blocks_original_deletion_and_restore_dependency(self):
        original, _ = self.resource(self.admin, '公共知识库')
        entry, _ = self.resource(self.admin, '公共知识库', libraryAssetIds=[{'id': original.id, 'label': '来源原件', 'role': 'source'}])
        self.client.force_login(self.admin, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.remove(original).status_code, 409)
        self.assertEqual(self.remove(entry).status_code, 200)
        self.assertEqual(self.remove(original).status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(self.restore(entry).status_code, 409)
        original.refresh_from_db()
        self.assertEqual(self.restore(original).status_code, 200)
        self.assertEqual(self.restore(entry).status_code, 200)

    def test_new_submission_does_not_include_papers_from_the_trash(self):
        resource, _ = self.resource()
        task = record(self.owner, 'tasks', title='独立训练', attachmentIds=[])
        current = project(self.owner, task)
        paper = record(self.owner, 'papers', title='已移入回收站论文', fileId=resource.id, projectId=current.id, scores=[None] * 7)
        self.assertEqual(self.remove(paper).status_code, 200)
        submission_id = 'submission_' + uuid.uuid4().hex
        data = {'id': submission_id, 'taskId': task.id, 'projectId': current.id}
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'taskSubmissions': [data]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        stored = Record.objects.get(pk=submission_id)
        self.assertEqual(stored.payload['paperIds'], [])
        self.assertEqual(stored.payload['snapshot']['paperSnapshots'], [])

    @override_settings(AI_API_KEY='isolated-placeholder-not-a-real-key')
    def test_trashed_competition_does_not_leave_hidden_ai_restriction(self):
        competition = record(self.owner, 'competitions', title='独立模拟', members='', status='active', aiPolicy='关闭 AI')
        # Only the validation boundary is tested. No fake model response or
        # network call is used to claim that AI itself works.
        with patch('platform_app.views.httpx.Client') as network:
            self.assertEqual(self.post('/api/ai/chat', {'messages': []}).status_code, 403)
            self.assertEqual(self.remove(competition).status_code, 200)
            self.assertEqual(self.post('/api/ai/chat', {'messages': []}).status_code, 400)
            network.assert_not_called()

    def test_started_competition_trash_detaches_only_project_marker_and_restore_merges_later_notes(self):
        competition, current = self.started_competition()
        before = copy.deepcopy(current.payload)
        initial_revision = current.revision
        blocked = self.remove(current)
        self.assertEqual(blocked.status_code, 409)
        self.assertIn('先将比赛移入回收站', blocked.json()['error']['message'])
        self.assertEqual(self.remove(competition).status_code, 200)
        competition.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(competition.payload['_deletedCompanionProjectId'], current.id)
        self.assertEqual(current.revision, initial_revision + 1)
        self.assertNotIn('competitionId', current.payload)
        self.assertEqual(current.payload, {k: v for k, v in before.items() if k != 'competitionId'})
        later = copy.deepcopy(current.payload)
        later['stages'][0]['content'] = '比赛回收后继续写的新正文，不得被旧快照覆盖'
        saved = self.client.patch('/api/workspace', json.dumps({'changes': {'projects': [{**later, '_revision': current.revision}]}}), content_type='application/json')
        self.assertEqual(saved.status_code, 200)
        current.refresh_from_db()
        before_restore_revision = current.revision
        self.assertEqual(self.restore(competition).status_code, 200)
        current.refresh_from_db()
        self.assertEqual(current.revision, before_restore_revision + 1)
        self.assertEqual(current.payload['competitionId'], competition.id)
        self.assertEqual(current.payload['stages'][0]['content'], later['stages'][0]['content'])
        self.assertEqual(current.payload['resourceIds'], before['resourceIds'])
        self.assertTrue(Audit.objects.filter(action='competition-project-detach', target=current.id).exists())
        self.assertTrue(Audit.objects.filter(action='competition-project-attach', target=current.id).exists())

    def test_competition_restore_requires_project_to_be_restored_first(self):
        competition, current = self.started_competition()
        self.assertEqual(self.remove(competition).status_code, 200)
        competition.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(self.remove(current).status_code, 200)
        response = self.restore(competition)
        self.assertEqual(response.status_code, 409)
        self.assertIn('先恢复项目', response.json()['error']['message'])
        current.refresh_from_db()
        self.assertEqual(self.restore(current).status_code, 200)
        self.assertEqual(self.restore(competition).status_code, 200)
        current.refresh_from_db()
        self.assertEqual(current.payload['competitionId'], competition.id)

    def test_competition_restore_does_not_replace_another_competition_relationship(self):
        competition, current = self.started_competition()
        self.assertEqual(self.remove(competition).status_code, 200)
        competition.refresh_from_db()
        current.refresh_from_db()
        other_id = 'competition_' + uuid.uuid4().hex
        updated_project = {**current.payload, 'competitionId': other_id, '_revision': current.revision}
        other = {'id': other_id, 'title': '后续另一比赛', 'members': '', 'projectId': current.id, 'status': 'active'}
        result = self.client.patch('/api/workspace', json.dumps({'changes': {'projects': [updated_project], 'competitions': [other]}}), content_type='application/json')
        self.assertEqual(result.status_code, 200)
        before = Record.objects.get(pk=current.pk)
        response = self.restore(competition)
        self.assertEqual(response.status_code, 409)
        current.refresh_from_db()
        self.assertEqual(current.payload, before.payload)
        self.assertEqual(current.revision, before.revision)
        self.assertEqual(current.payload['competitionId'], other_id)
        self.assertEqual(Record.objects.get(pk=competition.pk).scope, 'deleted')

    def test_submitted_competition_snapshot_blocks_deletion_without_detaching_project(self):
        competition, current = self.started_competition()
        task = record(self.owner, 'tasks', title='提交历史测试任务', attachmentIds=[])
        current.payload['taskId'] = task.id
        current.save()
        submission_id = 'submission_' + uuid.uuid4().hex
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'taskSubmissions': [{'id': submission_id, 'taskId': task.id, 'projectId': current.id}]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        before = copy.deepcopy(current.payload)
        revision = current.revision
        self.assertEqual(self.remove(competition).status_code, 409)
        current.refresh_from_db()
        competition.refresh_from_db()
        self.assertEqual(current.payload, before)
        self.assertEqual(current.revision, revision)
        self.assertEqual(competition.scope, 'private')
        self.assertEqual(Record.objects.get(pk=submission_id).payload['snapshot']['competitionId'], competition.id)

    def test_nested_project_reference_is_not_the_detachable_top_level_marker(self):
        competition, current = self.started_competition()
        current.payload['retainedHistory'] = {'competitionId': competition.id}
        current.save()
        self.assertEqual(self.remove(competition).status_code, 409)
        current.refresh_from_db()
        self.assertEqual(current.payload['competitionId'], competition.id)

    def test_competition_cannot_link_another_users_private_project(self):
        task = record(self.other, 'tasks', title='其他用户任务', attachmentIds=[])
        current = project(self.other, task)
        data = {'id': 'competition_' + uuid.uuid4().hex, 'title': '不能引用私有项目', 'members': '', 'projectId': current.id}
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'competitions': [data]}}), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Record.objects.filter(pk=data['id']).exists())

    def test_mentor_review_permission_does_not_allow_deleting_student_paper(self):
        resource, _ = self.resource()
        task = record(self.mentor, 'tasks', title='导师任务', attachmentIds=[])
        paper = record(self.owner, 'papers', title='学生论文', fileId=resource.id, scores=[None] * 7)
        record(self.owner, 'taskSubmissions', taskId=task.id, personId=str(self.owner.id), paperIds=[paper.id])
        self.assertTrue(editable(self.mentor, paper))
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.remove(paper).status_code, 404)

    def test_chat_message_attachments_cannot_disappear_from_history(self):
        team = record(self.mentor, 'teams', name='独立团队', members=[], fileIds=[], messages=[])
        Membership.objects.create(team=team, user=self.owner)
        room = ChatRoom.objects.create(key='team:' + team.id, title='独立会话', team=team, created_by=self.mentor)
        resource, _ = self.resource(chatRoomId=str(room.id))
        ChatMessage.objects.create(room=room, sender=self.owner, client_id=uuid.uuid4(), body='', attachments=[resource.id])
        response = self.remove(resource)
        self.assertEqual(response.status_code, 409)
        self.assertIn('聊天附件', response.json()['error']['message'])

    def test_unsent_deleted_chat_file_cannot_be_sent_or_restored_after_removal(self):
        team = record(self.mentor, 'teams', name='独立团队', members=[], fileIds=[], messages=[])
        Membership.objects.create(team=team, user=self.owner)
        room = ChatRoom.objects.create(key='team:' + team.id, title='独立会话', team=team, created_by=self.mentor)
        resource, _ = self.resource(chatRoomId=str(room.id))
        self.assertEqual(self.remove(resource).status_code, 200)
        response = self.post(f'/api/chat/rooms/{room.id}/messages', {'clientId': str(uuid.uuid4()), 'body': '', 'attachmentIds': [resource.id]})
        self.assertEqual(response.status_code, 403)
        Membership.objects.filter(team=team, user=self.owner).delete()
        resource.refresh_from_db()
        self.assertEqual(self.restore(resource).status_code, 404)
        self.assertEqual(Record.objects.get(pk=resource.pk).scope, 'deleted')

    def test_current_role_is_revalidated_before_restoring_private_teacher_resource(self):
        row, _ = self.resource(self.mentor, '教师私有')
        row.scope = 'teacher'
        row.save()
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.remove(row).status_code, 200)
        self.mentor.role = 'student'
        self.mentor.save()
        row.refresh_from_db()
        self.assertEqual(self.restore(row).status_code, 403)
        self.assertEqual(Record.objects.get(pk=row.pk).scope, 'deleted')

    def test_all_six_supported_collections_round_trip_with_original_data(self):
        resource, _ = self.resource()
        task = record(self.owner, 'tasks', title='不删除的练习任务', attachmentIds=[])
        current = project(self.owner, task)
        paper = record(self.owner, 'papers', title='独立论文', fileId=resource.id, projectId='', scores=[None] * 7)
        competition = record(self.owner, 'competitions', title='独立模拟', members='甲：建模\n乙：写作')
        conversation = record(self.owner, 'conversations', title='独立对话', messages=[])
        for row in [self.draft(), paper, current, competition, conversation]:
            with self.subTest(collection=row.collection):
                self.assertEqual(self.remove(row).status_code, 200)
                row.refresh_from_db()
                self.assertEqual(self.restore(row).status_code, 200)
        # The original is referenced by the restored paper, so remove the paper
        # first to test the file's independent delete/restore round trip.
        paper.refresh_from_db()
        self.assertEqual(self.remove(paper).status_code, 200)
        self.assertEqual(self.remove(resource).status_code, 200)
        resource.refresh_from_db()
        self.assertEqual(self.restore(resource).status_code, 200)

    def test_reference_lookup_locks_row_inside_atomic_workspace_transaction(self):
        row = self.draft()
        # TestCase itself owns a transaction. The explicit locking contract is
        # exercised locally; PostgreSQL verifies actual concurrent serialization.
        with patch('platform_app.domain.get_record', wraps=get_record) as lookup:
            self.assertEqual(reference(self.owner, row.id).id, row.id)
            self.assertTrue(lookup.call_args.kwargs['lock'])

    def test_unverified_and_anonymous_accounts_cannot_mutate_or_inspect_trash(self):
        row = self.draft()
        anonymous = Client()
        self.assertEqual(anonymous.get('/api/records/trash').status_code, 403)
        unverified = person('trash-unverified', verified=False)
        self.client.force_login(unverified, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/records/trash').status_code, 403)
        self.assertEqual(self.remove(row).status_code, 403)

    def test_csrf_and_account_binding_are_required_for_delete(self):
        row = self.draft()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner, backend='django.contrib.auth.backends.ModelBackend')
        url = f'/api/records/writingDrafts/{row.id}/delete'
        self.assertEqual(strict.post(url, json.dumps({'revision': 1}), content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post(url, json.dumps({'revision': 1}), content_type='application/json', HTTP_X_MM_ACCOUNT=str(self.other.id)).status_code, 409)

    def test_project_detach_is_revision_checked_idempotent_and_keeps_original(self):
        first, asset = self.resource()
        second, _ = self.resource()
        task = record(self.owner, 'tasks', title='独立任务', attachmentIds=[])
        current = project(self.owner, task)
        current.payload['resourceIds'] = [first.id, second.id]
        current.save()
        before = copy.deepcopy(current.payload)
        response = self.detach(current, first.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['revision'], 2)
        self.assertTrue(self.detach(current, first.id).json()['duplicate'])
        current.refresh_from_db()
        self.assertEqual(current.payload['resourceIds'], [second.id])
        self.assertEqual(current.payload['stages'], before['stages'])
        self.assertEqual(Audit.objects.filter(action='detach-file:projects', target=current.id).count(), 1)
        self.assertTrue(asset.file.storage.exists(asset.file.name))
        self.assertEqual(Record.objects.get(pk=first.id).scope, 'private')
        self.assertEqual(self.remove(first).status_code, 200)

    def test_task_detach_does_not_modify_existing_student_project_or_submission(self):
        resource, _ = self.resource(self.mentor)
        task = record(self.mentor, 'tasks', title='全校训练', audience='school', attachmentIds=[resource.id])
        task.scope = 'school'
        task.save()
        current = project(self.owner, task)
        current.payload['resourceIds'] = [resource.id]
        current.save()
        submission = record(self.owner, 'taskSubmissions', taskId=task.id, projectId=current.id, snapshot=copy.deepcopy(current.payload))
        before_project, before_submission = copy.deepcopy(current.payload), copy.deepcopy(submission.payload)
        self.assertTrue(can_read(self.owner, resource))
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.detach(task, resource.id).status_code, 200)
        task.refresh_from_db()
        current.refresh_from_db()
        submission.refresh_from_db()
        self.assertEqual(task.payload['attachmentIds'], [])
        self.assertEqual(current.payload, before_project)
        self.assertEqual(submission.payload, before_submission)
        self.assertFalse(can_read(type(self.owner).objects.get(pk=self.owner.pk), resource))
        # The immutable project/submission references still retain the original.
        self.assertEqual(self.remove(resource).status_code, 409)

    def team_with_files(self, published=False):
        resource, asset = self.resource(self.mentor)
        other, _ = self.resource(self.mentor)
        team = record(self.mentor, 'teams', name='文件协作团队', members=[], fileIds=[resource.id, other.id], messages=[{'id': 'message_' + uuid.uuid4().hex, 'title': '团队消息', 'body': '独立附件测试', 'status': 'published' if published else 'draft', 'attachmentIds': [resource.id, other.id], 'recipientIds': []}])
        Membership.objects.create(team=team, user=self.owner)
        resource.team = team
        resource.payload['teamId'] = team.id
        resource.save()
        other.team = team
        other.save()
        return team, resource, other, asset

    def published_team_after_member_removal(self, pending=False):
        team, resource, other, _ = self.team_with_files()
        member_id, peer_id = 'member_' + uuid.uuid4().hex, 'member_' + uuid.uuid4().hex
        team.payload['members'] = [
            {'id': member_id, 'name': '待移除成员', 'identifier': self.owner.email, 'accountId': str(self.owner.id)},
            {'id': peer_id, 'name': '保留成员', 'identifier': self.other.email, 'accountId': str(self.other.id)},
        ]
        team.payload['messages'][0]['recipientIds'] = [member_id]
        if pending:
            team.payload['messages'].append({
                'id': 'message_' + uuid.uuid4().hex, 'title': '尚未发布', 'body': '撤权后不应发送',
                'status': 'draft', 'attachmentIds': [], 'recipientIds': [member_id],
            })
        team.save()
        Membership.objects.create(team=team, user=self.other)
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        response = self.post(f'/api/teams/{team.id}/publish', {'messageId': team.payload['messages'][0]['id'], 'revision': team.revision})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recipients'], 1)
        self.assertEqual(self.post(f'/api/teams/{team.id}/members/{self.owner.id}/remove', {}).status_code, 200)
        team.refresh_from_db()
        self.assertFalse(Membership.objects.filter(team=team, user=self.owner).exists())
        self.assertEqual([m['id'] for m in team.payload['members']], [peer_id])
        return team, resource, other, member_id, peer_id

    def test_published_history_survives_member_removal_then_real_upload_and_team_save(self):
        team, resource, other, member_id, peer_id = self.published_team_after_member_removal()
        original_message = copy.deepcopy(team.payload['messages'][0])
        note = Record.objects.get(collection='notifications', team=team)
        original_note = copy.deepcopy(note.payload)
        before_mail = MailJob.objects.count()
        new_id = 'resource_' + uuid.uuid4().hex
        contents = b'new team file after member removal'
        upload = self.client.post('/api/files', {
            'file': SimpleUploadedFile('after-removal.txt', contents),
            'metadata': json.dumps({'id': new_id, 'kind': 'attachment', 'scope': '个人资料'}),
        })
        self.assertEqual(upload.status_code, 201)
        changed = copy.deepcopy(team.payload)
        changed['fileIds'].append(new_id)
        changed['description'] = '保留已发布通知历史，继续协作'
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'teams': [{**changed, '_revision': team.revision}]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        team.refresh_from_db()
        note.refresh_from_db()
        self.assertEqual(team.payload['messages'][0], original_message)
        self.assertEqual(team.payload['messages'][0]['recipientIds'], [member_id])
        self.assertEqual(note.payload, original_note)
        self.assertEqual(MailJob.objects.count(), before_mail)
        self.assertFalse(Membership.objects.filter(team=team, user=self.owner).exists())
        self.client.force_login(self.owner, backend='django.contrib.auth.backends.ModelBackend')
        for file_id in [resource.id, other.id, new_id]:
            self.assertEqual(self.client.get('/api/files/' + file_id).status_code, 404)
        self.client.force_login(self.other, backend='django.contrib.auth.backends.ModelBackend')
        download = self.client.get('/api/files/' + new_id)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), contents)

    def test_removed_recipient_cannot_be_added_to_draft_or_rewrite_published_history(self):
        team, _, _, member_id, peer_id = self.published_team_after_member_removal()
        before = copy.deepcopy(team.payload)
        invalid_draft = {'id': 'message_' + uuid.uuid4().hex, 'title': '无效新草稿', 'body': '不得重新发给移除者', 'status': 'draft', 'attachmentIds': [], 'recipientIds': [member_id]}
        changed = copy.deepcopy(before)
        changed['messages'].append(invalid_draft)
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'teams': [{**changed, '_revision': team.revision}]}}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('消息收件成员无效', response.json()['error']['message'])
        for field, value in [('body', '改写历史正文'), ('recipientIds', [])]:
            changed = copy.deepcopy(before)
            changed['messages'][0][field] = value
            response = self.client.patch('/api/workspace', json.dumps({'changes': {'teams': [{**changed, '_revision': team.revision}]}}), content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertIn('已发布消息不能', response.json()['error']['message'])
        team.refresh_from_db()
        self.assertEqual(team.payload, before)
        before_mail, before_notes = MailJob.objects.count(), Record.objects.filter(collection='notifications', team=team).count()
        duplicate = self.post(f'/api/teams/{team.id}/publish', {'messageId': before['messages'][0]['id'], 'revision': team.revision})
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()['duplicate'])
        self.assertEqual(MailJob.objects.count(), before_mail)
        self.assertEqual(Record.objects.filter(collection='notifications', team=team).count(), before_notes)
        valid_draft = {**invalid_draft, 'id': 'message_' + uuid.uuid4().hex, 'title': '当前成员新通知', 'recipientIds': [peer_id]}
        changed = copy.deepcopy(before)
        changed['messages'].append(valid_draft)
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'teams': [{**changed, '_revision': team.revision}]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        team.refresh_from_db()
        self.assertEqual(self.post(f'/api/teams/{team.id}/publish', {'messageId': valid_draft['id'], 'revision': team.revision}).status_code, 200)
        self.assertEqual(Record.objects.filter(collection='notifications', team=team, payload__personId=str(self.owner.id)).count(), 1)
        self.assertEqual(Record.objects.filter(collection='notifications', team=team, payload__personId=str(self.other.id)).count(), 1)

    def test_saved_unpublished_draft_cannot_send_after_recipient_removal(self):
        team, _, _, _, _ = self.published_team_after_member_removal(pending=True)
        before = copy.deepcopy(team.payload)
        before_mail = MailJob.objects.count()
        response = self.post(f'/api/teams/{team.id}/publish', {'messageId': team.payload['messages'][1]['id'], 'revision': team.revision})
        self.assertEqual(response.status_code, 400)
        team.refresh_from_db()
        self.assertEqual(team.payload, before)
        self.assertEqual(MailJob.objects.count(), before_mail)
        self.assertEqual(Record.objects.filter(collection='notifications', team=team).count(), 1)

    def test_team_detach_cleans_draft_and_revokes_obsolete_file_share(self):
        team, resource, other, asset = self.team_with_files()
        self.assertTrue(can_read(self.owner, resource))
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.detach(team, resource.id).status_code, 200)
        team.refresh_from_db()
        resource.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(team.payload['fileIds'], [other.id])
        self.assertEqual(team.payload['messages'][0]['attachmentIds'], [other.id])
        self.assertIsNone(resource.team_id)
        self.assertNotIn('teamId', resource.payload)
        self.assertEqual(resource.revision, 2)
        self.assertEqual(other.team_id, team.id)
        self.assertFalse(can_read(type(self.owner).objects.get(pk=self.owner.pk), resource))
        self.assertTrue(can_read(self.owner, other))
        self.assertTrue(asset.file.storage.exists(asset.file.name))
        self.assertEqual(self.remove(resource).status_code, 200)
        workspace = self.client.get('/api/workspace').json()
        self.assertNotIn('_lastDetachedFile', next(row for row in workspace['teams'] if row['id'] == team.id))

    def test_team_detach_keeps_independent_task_authorization(self):
        team, resource, other, _ = self.team_with_files()
        task = record(self.mentor, 'tasks', title='独立学校任务', attachmentIds=[resource.id], audience='school')
        task.scope = 'school'
        task.save()
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.detach(team, resource.id).status_code, 200)
        resource.refresh_from_db()
        self.assertIsNone(resource.team_id)
        self.assertTrue(can_read(type(self.owner).objects.get(pk=self.owner.pk), resource))
        self.assertEqual(self.remove(resource).status_code, 409)

    def test_published_team_message_blocks_detach_without_any_partial_changes(self):
        team, resource, other, _ = self.team_with_files(published=True)
        before = copy.deepcopy(team.payload)
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        response = self.detach(team, resource.id)
        self.assertEqual(response.status_code, 409)
        self.assertIn('团队通知', response.json()['error']['message'])
        team.refresh_from_db()
        resource.refresh_from_db()
        self.assertEqual(team.payload, before)
        self.assertEqual(team.revision, 1)
        self.assertEqual(resource.team_id, team.id)
        self.assertEqual(resource.revision, 1)

    def test_existing_published_notification_also_blocks_detach(self):
        team, resource, other, _ = self.team_with_files()
        team.payload['messages'] = []
        team.save()
        note = record(self.mentor, 'notifications', title='已发布通知', attachmentIds=[resource.id], personId=str(self.owner.id), teamId=team.id)
        note.team = team
        note.save()
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.detach(team, resource.id).status_code, 409)
        self.assertEqual(Record.objects.get(pk=resource.pk).team_id, team.id)

    def test_ordinary_team_workspace_save_also_revokes_removed_file_share(self):
        team, resource, other, _ = self.team_with_files()
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        changed = copy.deepcopy(team.payload)
        changed['fileIds'] = [other.id]
        changed['messages'][0]['attachmentIds'] = [other.id]
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'teams': [{**changed, '_revision': team.revision}]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        resource.refresh_from_db()
        self.assertIsNone(resource.team_id)
        self.assertNotIn('teamId', resource.payload)
        self.assertEqual(response.json()['versions']['resources/' + resource.id], resource.revision)
        self.assertFalse(can_read(type(self.owner).objects.get(pk=self.owner.pk), resource))

    def test_workspace_cannot_bypass_published_history_to_remove_team_file(self):
        team, resource, other, _ = self.team_with_files(published=True)
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        changed = {**team.payload, 'fileIds': [other.id], 'messages': [], '_revision': team.revision}
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'teams': [changed]}}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('已发布消息不能删除', response.json()['error']['message'])
        team.refresh_from_db()
        resource.refresh_from_db()
        self.assertIn(resource.id, team.payload['fileIds'])
        self.assertEqual(resource.team_id, team.id)

    def test_member_or_unrelated_owner_cannot_detach_parent_file(self):
        team, resource, other, _ = self.team_with_files()
        self.assertEqual(self.detach(team, resource.id).status_code, 404)
        self.client.force_login(self.other, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.detach(team, resource.id).status_code, 404)
        self.assertEqual(Record.objects.get(pk=team.pk).payload['fileIds'], [resource.id, other.id])

    def test_admin_can_detach_file_without_receiving_private_file_body(self):
        team, resource, other, _ = self.team_with_files()
        self.client.force_login(self.admin, backend='django.contrib.auth.backends.ModelBackend')
        response = self.detach(team, resource.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('可检索的独立样例', response.content.decode())
        self.assertIsNone(Record.objects.get(pk=resource.pk).team_id)

    def test_detach_rejects_stale_revision_and_unknown_link_without_touching_file(self):
        team, resource, other, _ = self.team_with_files()
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        team.revision = 3
        team.save()
        self.assertEqual(self.detach(team, resource.id, 2).status_code, 409)
        self.assertEqual(self.detach(team, 'missing_fixture_file').status_code, 400)
        team.refresh_from_db()
        self.assertEqual(team.payload['fileIds'], [resource.id, other.id])
        self.assertEqual(Record.objects.get(pk=resource.pk).team_id, team.id)

    def test_stale_resource_team_metadata_cannot_regrant_removed_share_at_new_revision(self):
        team, resource, other, _ = self.team_with_files()
        cached = copy.deepcopy(resource.payload)
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        changed = copy.deepcopy(team.payload)
        changed['fileIds'] = [other.id]
        changed['messages'][0]['attachmentIds'] = [other.id]
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'teams': [{**changed, '_revision': team.revision}]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        version = response.json()['versions']['resources/' + resource.id]
        # A browser may accept new identity/revision metadata while retaining
        # the old payload. Editing a description must not change sharing.
        result = self.client.patch('/api/workspace', json.dumps({'changes': {'resources': [{**cached, 'description': '移除后继续修改说明', '_revision': version}]}}), content_type='application/json')
        self.assertEqual(result.status_code, 200)
        resource.refresh_from_db()
        self.assertIsNone(resource.team_id)
        self.assertNotIn('teamId', resource.payload)
        self.assertEqual(resource.payload['description'], '移除后继续修改说明')
        self.assertFalse(can_read(type(self.owner).objects.get(pk=self.owner.pk), resource))
        self.client.force_login(self.owner, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/files/' + resource.id).status_code, 404)

    def test_orphan_team_foreign_key_does_not_itself_grant_resource_access(self):
        team, resource, other, _ = self.team_with_files()
        team.payload['fileIds'] = [other.id]
        team.save()
        self.assertEqual(resource.team_id, team.id)
        self.assertFalse(can_read(type(self.owner).objects.get(pk=self.owner.pk), resource))
        self.assertTrue(can_read(self.mentor, resource))

    def test_resource_metadata_edit_does_not_remove_a_valid_team_file_share(self):
        team, resource, other, _ = self.team_with_files()
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        changed = {**resource.payload, 'description': '合法团队分享保留', '_revision': resource.revision}
        response = self.client.patch('/api/workspace', json.dumps({'changes': {'resources': [changed]}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        resource.refresh_from_db()
        self.assertEqual(resource.team_id, team.id)
        self.assertTrue(can_read(type(self.owner).objects.get(pk=self.owner.pk), resource))

    def test_restore_rechecks_dependencies_after_wait_before_locking_parent(self):
        first, _ = self.resource()
        second, _ = self.resource()
        task = record(self.owner, 'tasks', title='恢复依赖复核', attachmentIds=[])
        current = project(self.owner, task)
        current.payload['resourceIds'] = [first.id]
        current.save()
        self.assertEqual(self.remove(current).status_code, 200)
        current.refresh_from_db()
        from .deletion import lock_restore_dependencies

        def dependency_changed(candidate):
            lock_restore_dependencies(candidate)
            changed = copy.deepcopy(candidate.payload)
            changed['resourceIds'] = [second.id]
            Record.objects.filter(pk=candidate.pk).update(payload=changed)

        # Deterministic local validation of the dependency-signature guard.
        # Actual two-connection lock ordering is exercised only on PostgreSQL.
        with patch('platform_app.deletion.lock_restore_dependencies', side_effect=dependency_changed):
            response = self.restore(current)
        self.assertEqual(response.status_code, 409)
        current.refresh_from_db()
        self.assertEqual(current.scope, 'deleted')
        self.assertEqual(current.payload['resourceIds'], [first.id])


@skipUnless(connection.vendor == 'postgresql', 'Row-lock concurrency requires the Linux PostgreSQL test database; SQLite does not prove this.')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MAIL_TRANSPORT='local', AI_API_KEY='')
class PostgreSQLTrashReferenceRaceTests(TransactionTestCase):
    def setUp(self):
        self.owner = person('trash-race-owner')
        self.resource = record(self.owner, 'resources', name='race-fixture.txt', kind='knowledge', scope='个人资料', text='独立并发样例')

    def run_in_connection(self, operation):
        close_old_connections()
        try:
            return operation()
        finally:
            connection.close()

    def delete_response(self, row=None):
        from .deletion import remove
        row = row or self.resource
        request = APIRequestFactory().post('/api/records/' + row.collection + '/' + row.id + '/delete', {'revision': row.revision}, format='json')
        force_authenticate(request, self.owner)
        return remove(request, row.collection, row.id)

    def started_competition(self):
        competition_id, project_id = 'competition_' + uuid.uuid4().hex, 'project_' + uuid.uuid4().hex
        initial = {'id': competition_id, 'title': '并发模拟比赛', 'members': '', 'status': 'ready', 'hours': 6}
        save_workspace(self.owner, {'competitions': [initial]}, {})
        payload = {'id': project_id, 'title': initial['title'], 'competitionId': competition_id, 'resourceIds': [],
                   'stages': [{'title': str(i), 'content': '并发保留正文', 'done': False} for i in range(8)]}
        save_workspace(self.owner, {'projects': [payload], 'competitions': [{**initial, 'projectId': project_id, 'status': 'active', '_revision': 1}]}, {})
        return Record.objects.get(pk=competition_id), Record.objects.get(pk=project_id)

    def test_reference_wins_then_delete_waits_and_detects_committed_dependency(self):
        reference_locked = threading.Event()
        release_reference = threading.Event()
        delete_attempted = threading.Event()

        def create_reference():
            with transaction.atomic():
                reference(self.owner, self.resource.id, 'resources')
                reference_locked.set()
                if not release_reference.wait(8):
                    raise AssertionError('Fixture reference release timed out')
                record(self.owner, 'projects', title='并发关联', resourceIds=[self.resource.id])

        def delete():
            delete_attempted.set()
            return self.delete_response().status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            saving = pool.submit(self.run_in_connection, create_reference)
            self.assertTrue(reference_locked.wait(5))
            removing = pool.submit(self.run_in_connection, delete)
            try:
                self.assertTrue(delete_attempted.wait(5))
                # PostgreSQL must keep deletion blocked on the referenced row.
                self.assertFalse(removing.done())
            finally:
                release_reference.set()
            saving.result(timeout=10)
            self.assertEqual(removing.result(timeout=10), 409)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.scope, 'private')

    def test_delete_wins_then_reference_waits_and_cannot_refer_to_deleted_file(self):
        delete_locked = threading.Event()
        release_delete = threading.Event()
        reference_attempted = threading.Event()

        def delete():
            with transaction.atomic():
                result = self.delete_response()
                if result.status_code != 200:
                    raise AssertionError('Fixture delete did not succeed')
                delete_locked.set()
                if not release_delete.wait(8):
                    raise AssertionError('Fixture deletion release timed out')

        def create_reference():
            reference_attempted.set()
            with transaction.atomic():
                try:
                    reference(self.owner, self.resource.id, 'resources')
                except NotFound:
                    return 'rejected'
                record(self.owner, 'projects', title='不应创建的关联', resourceIds=[self.resource.id])
                return 'created'

        with ThreadPoolExecutor(max_workers=2) as pool:
            removing = pool.submit(self.run_in_connection, delete)
            self.assertTrue(delete_locked.wait(5))
            saving = pool.submit(self.run_in_connection, create_reference)
            try:
                self.assertTrue(reference_attempted.wait(5))
                self.assertFalse(saving.done())
            finally:
                release_delete.set()
            removing.result(timeout=10)
            self.assertEqual(saving.result(timeout=10), 'rejected')
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.scope, 'deleted')
        self.assertFalse(Record.objects.filter(collection='projects').exists())

    def test_competition_only_save_uses_project_first_lock_order_and_trash_sees_new_revision(self):
        competition, current = self.started_competition()
        saving_locked, release_save, deletion_attempted = threading.Event(), threading.Event(), threading.Event()

        def save_competition():
            with transaction.atomic():
                save_workspace(self.owner, {'competitions': [{**competition.payload, 'hours': 7, '_revision': competition.revision}]}, {})
                saving_locked.set()
                if not release_save.wait(8):
                    raise AssertionError('Fixture competition save release timed out')

        def delete():
            deletion_attempted.set()
            return self.delete_response(competition).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            saving = pool.submit(self.run_in_connection, save_competition)
            self.assertTrue(saving_locked.wait(5))
            removing = pool.submit(self.run_in_connection, delete)
            try:
                self.assertTrue(deletion_attempted.wait(5))
                self.assertFalse(removing.done())
            finally:
                release_save.set()
            saving.result(timeout=10)
            self.assertEqual(removing.result(timeout=10), 409)
        competition.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(competition.payload['hours'], 7)
        self.assertEqual(competition.scope, 'private')
        self.assertEqual(current.payload['competitionId'], competition.id)

    def test_competition_trash_wins_then_waiting_save_cannot_resurrect_pair(self):
        competition, current = self.started_competition()
        deleted_locked, release_delete, saving_attempted = threading.Event(), threading.Event(), threading.Event()

        def delete():
            with transaction.atomic():
                result = self.delete_response(competition)
                if result.status_code != 200:
                    raise AssertionError('Fixture competition deletion failed')
                deleted_locked.set()
                if not release_delete.wait(8):
                    raise AssertionError('Fixture competition deletion release timed out')

        def save_competition():
            saving_attempted.set()
            try:
                save_workspace(self.owner, {'competitions': [{**competition.payload, 'hours': 7, '_revision': competition.revision}]}, {})
            except PermissionDenied:
                return 'rejected'
            return 'saved'

        with ThreadPoolExecutor(max_workers=2) as pool:
            removing = pool.submit(self.run_in_connection, delete)
            self.assertTrue(deleted_locked.wait(5))
            saving = pool.submit(self.run_in_connection, save_competition)
            try:
                self.assertTrue(saving_attempted.wait(5))
                self.assertFalse(saving.done())
            finally:
                release_delete.set()
            removing.result(timeout=10)
            self.assertEqual(saving.result(timeout=10), 'rejected')
        competition.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(competition.scope, 'deleted')
        self.assertNotIn('competitionId', current.payload)
        self.assertEqual(current.payload['stages'][0]['content'], '并发保留正文')

    def team_file(self):
        self.owner.role = 'mentor'
        self.owner.save()
        team = record(self.owner, 'teams', name='并发附件团队', description='', members=[], messages=[], fileIds=[self.resource.id])
        self.resource.team = team
        self.resource.save()
        return team

    def detach_response(self, team):
        from .deletion import detach_file
        request = APIRequestFactory().post('/api/records/teams/' + team.id + '/detach-file', {'fileId': self.resource.id, 'revision': team.revision}, format='json')
        force_authenticate(request, self.owner)
        return detach_file(request, 'teams', team.id)

    def test_team_workspace_save_then_detach_share_serializes_and_rejects_stale_request(self):
        team = self.team_file()
        saved_locked, release_save, detach_attempted = threading.Event(), threading.Event(), threading.Event()

        def save_team():
            with transaction.atomic():
                save_workspace(self.owner, {'teams': [{**team.payload, 'description': '另一页先保存的团队说明', '_revision': team.revision}]}, {})
                saved_locked.set()
                if not release_save.wait(8):
                    raise AssertionError('Fixture team save release timed out')

        def detach():
            detach_attempted.set()
            return self.detach_response(team).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            saving = pool.submit(self.run_in_connection, save_team)
            self.assertTrue(saved_locked.wait(5))
            detaching = pool.submit(self.run_in_connection, detach)
            try:
                self.assertTrue(detach_attempted.wait(5))
                self.assertFalse(detaching.done())
            finally:
                release_save.set()
            saving.result(timeout=10)
            self.assertEqual(detaching.result(timeout=10), 409)
        team.refresh_from_db()
        self.resource.refresh_from_db()
        self.assertEqual(team.payload['description'], '另一页先保存的团队说明')
        self.assertEqual(team.payload['fileIds'], [self.resource.id])
        self.assertEqual(self.resource.team_id, team.id)

    def test_team_detach_then_waiting_workspace_save_cannot_restore_revoked_share(self):
        team = self.team_file()
        detached_locked, release_detach, save_attempted = threading.Event(), threading.Event(), threading.Event()

        def detach():
            with transaction.atomic():
                if self.detach_response(team).status_code != 200:
                    raise AssertionError('Fixture detach failed')
                detached_locked.set()
                if not release_detach.wait(8):
                    raise AssertionError('Fixture detach release timed out')

        def save_team():
            save_attempted.set()
            try:
                save_workspace(self.owner, {'teams': [{**team.payload, 'description': '不应覆盖移除动作', '_revision': team.revision}]}, {})
            except Conflict:
                return 'conflict'
            return 'saved'

        with ThreadPoolExecutor(max_workers=2) as pool:
            detaching = pool.submit(self.run_in_connection, detach)
            self.assertTrue(detached_locked.wait(5))
            saving = pool.submit(self.run_in_connection, save_team)
            try:
                self.assertTrue(save_attempted.wait(5))
                self.assertFalse(saving.done())
            finally:
                release_detach.set()
            detaching.result(timeout=10)
            self.assertEqual(saving.result(timeout=10), 'conflict')
        team.refresh_from_db()
        self.resource.refresh_from_db()
        self.assertEqual(team.payload['fileIds'], [])
        self.assertIsNone(self.resource.team_id)

    def restore_response(self, row):
        from .deletion import restore
        request = APIRequestFactory().post('/api/records/' + row.collection + '/' + row.id + '/restore', {'revision': row.revision}, format='json')
        force_authenticate(request, self.owner)
        return restore(request, row.collection, row.id)

    def trashed_parent(self, collection):
        if collection == 'projects':
            row = record(self.owner, collection, title='含原件的恢复项目', resourceIds=[self.resource.id], stages=[{'title': str(i), 'content': '恢复前保留正文', 'done': False} for i in range(8)])
        elif collection == 'competitions':
            row = record(self.owner, collection, title='含原件的恢复比赛', attachmentIds=[self.resource.id], members='', rules='', hours=1, status='ready')
        else:
            row = record(self.owner, collection, title='含原件的恢复论文', fileId=self.resource.id, projectId='', scores=[None] * 7)
        self.assertEqual(self.delete_response(row).status_code, 200)
        row.refresh_from_db()
        return row

    def worker_pid(self, values, key):
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()')
            values[key] = cursor.fetchone()[0]

    def wait_for_postgres_lock(self, pid):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s', [pid])
                row = cursor.fetchone()
            if row and row[0] == 'Lock':
                return
            time.sleep(.02)
        self.fail('Fixture worker did not reach its PostgreSQL row lock')

    def restore_stale_patch_race(self, collection, restore_first):
        parent = self.trashed_parent(collection)
        stale = {**parent.payload, 'title': '过期页面不应覆盖恢复正文', '_revision': 1}
        resource_payload = {**self.resource.payload, 'description': '应整体回滚的资源变更', '_revision': self.resource.revision}
        held, release, attempted = threading.Event(), threading.Event(), threading.Event()
        pids = {}

        if restore_first:
            def first():
                with transaction.atomic():
                    result = self.restore_response(parent)
                    if result.status_code != 200:
                        raise AssertionError('Fixture parent restore failed')
                    held.set()
                    if not release.wait(8):
                        raise AssertionError('Fixture restored parent release timed out')

            def second():
                self.worker_pid(pids, 'second')
                attempted.set()
                try:
                    save_workspace(self.owner, {'resources': [resource_payload], collection: [stale]}, {})
                except Conflict:
                    return 'conflict'
                return 'saved'
        else:
            def first():
                with transaction.atomic():
                    Record.objects.select_for_update(of=('self',)).get(pk=self.resource.id)
                    held.set()
                    if not release.wait(8):
                        raise AssertionError('Fixture stale patch release timed out')
                    try:
                        save_workspace(self.owner, {'resources': [resource_payload], collection: [stale]}, {})
                    except PermissionDenied:
                        return 'rejected'
                    return 'saved'

            def second():
                self.worker_pid(pids, 'second')
                attempted.set()
                return self.restore_response(parent).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(self.run_in_connection, first)
            self.assertTrue(held.wait(5))
            second_future = pool.submit(self.run_in_connection, second)
            try:
                self.assertTrue(attempted.wait(5))
                # Wait for an observed PostgreSQL lock, so the old parent-first
                # restore would deterministically deadlock when PATCH resumes.
                self.wait_for_postgres_lock(pids['second'])
            finally:
                release.set()
            first_result = first_future.result(timeout=10)
            second_result = second_future.result(timeout=10)
        if restore_first:
            self.assertEqual(second_result, 'conflict')
        else:
            self.assertEqual(first_result, 'rejected')
            self.assertEqual(second_result, 200)
        parent.refresh_from_db()
        self.resource.refresh_from_db()
        self.assertEqual(parent.scope, 'private')
        self.assertNotEqual(parent.payload['title'], stale['title'])
        self.assertNotIn('应整体回滚的资源变更', self.resource.payload.get('description', ''))

    def test_resource_parent_patch_then_restore_project_has_no_reverse_lock(self):
        self.restore_stale_patch_race('projects', restore_first=False)

    def test_restore_project_then_resource_parent_patch_keeps_atomic_rollback(self):
        self.restore_stale_patch_race('projects', restore_first=True)

    def test_resource_parent_patch_then_restore_paper_has_no_reverse_lock(self):
        self.restore_stale_patch_race('papers', restore_first=False)

    def test_restore_paper_then_resource_parent_patch_keeps_atomic_rollback(self):
        self.restore_stale_patch_race('papers', restore_first=True)

    def test_resource_parent_patch_then_restore_competition_has_no_reverse_lock(self):
        self.restore_stale_patch_race('competitions', restore_first=False)

    def test_restore_competition_then_resource_parent_patch_keeps_atomic_rollback(self):
        self.restore_stale_patch_race('competitions', restore_first=True)

    def test_restore_rejects_changed_dependencies_after_observed_resource_lock_wait(self):
        parent = self.trashed_parent('projects')
        other = record(self.owner, 'resources', name='new-dependency.txt', kind='knowledge', scope='个人资料', text='后续关联的原件')
        held, release, attempted = threading.Event(), threading.Event(), threading.Event()
        pids = {}

        def restore_and_edit_first():
            with transaction.atomic():
                Record.objects.select_for_update(of=('self',)).get(pk=self.resource.id)
                held.set()
                if not release.wait(8):
                    raise AssertionError('Fixture changed dependency release timed out')
                if self.restore_response(parent).status_code != 200:
                    raise AssertionError('Fixture first restore failed')
                current = Record.objects.get(pk=parent.pk)
                save_workspace(self.owner, {'projects': [{**current.payload, 'resourceIds': [other.id], 'title': '先恢复并编辑后的项目', '_revision': current.revision}]}, {})

        def restore_stale():
            self.worker_pid(pids, 'second')
            attempted.set()
            return self.restore_response(parent).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.run_in_connection, restore_and_edit_first)
            self.assertTrue(held.wait(5))
            second = pool.submit(self.run_in_connection, restore_stale)
            try:
                self.assertTrue(attempted.wait(5))
                self.wait_for_postgres_lock(pids['second'])
            finally:
                release.set()
            first.result(timeout=10)
            self.assertEqual(second.result(timeout=10), 409)
        parent.refresh_from_db()
        self.assertEqual(parent.scope, 'private')
        self.assertEqual(parent.payload['resourceIds'], [other.id])
        self.assertEqual(parent.payload['title'], '先恢复并编辑后的项目')


@skipUnless(connection.vendor == 'postgresql', 'Publishing/removing a member concurrently requires real PostgreSQL row locks.')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MAIL_TRANSPORT='local', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', AI_API_KEY='')
class PostgreSQLPublishMemberRaceTests(TransactionTestCase):
    run_in_connection = PostgreSQLTrashReferenceRaceTests.run_in_connection
    worker_pid = PostgreSQLTrashReferenceRaceTests.worker_pid
    wait_for_postgres_lock = PostgreSQLTrashReferenceRaceTests.wait_for_postgres_lock

    def setUp(self):
        self.mentor = person('publish-race-mentor', 'mentor')
        self.student = person('publish-race-student')
        self.member_id, self.message_id = 'member_' + uuid.uuid4().hex, 'message_' + uuid.uuid4().hex
        self.team = record(self.mentor, 'teams', name='发布与撤销并发团队', members=[{'id': self.member_id, 'name': '独立学生', 'email': self.student.email, 'identifier': self.student.email, 'accountId': str(self.student.id)}], fileIds=[], messages=[{'id': self.message_id, 'title': '独立通知', 'body': '真实后端发布与成员移除并发测试', 'recipientIds': [self.member_id], 'attachmentIds': [], 'status': 'draft'}])
        Membership.objects.create(team=self.team, user=self.student)

    def publish_response(self):
        from .views import publish
        request = APIRequestFactory().post('/api/teams/' + self.team.id + '/publish', {'messageId': self.message_id, 'revision': self.team.revision}, format='json')
        force_authenticate(request, self.mentor)
        return publish(request, self.team.id)

    def remove_response(self):
        from .chat import remove_member
        request = APIRequestFactory().post('/api/teams/' + self.team.id + '/members/' + str(self.student.id) + '/remove', {}, format='json')
        force_authenticate(request, self.mentor)
        return remove_member(request, self.team.id, self.student.id)

    def publish_remove_race(self, removal_first):
        held, release, attempted = threading.Event(), threading.Event(), threading.Event()
        pids = {}

        def first():
            with transaction.atomic():
                # Hold exactly the first User lock in the real removal/publish
                # handlers. The second handler must wait here before taking Team.
                type(self.student).objects.select_for_update().get(pk=self.student.id)
                held.set()
                if not release.wait(8):
                    raise AssertionError('Fixture member/publish release timed out')
                return (self.remove_response() if removal_first else self.publish_response()).status_code

        def second():
            self.worker_pid(pids, 'second')
            attempted.set()
            return (self.publish_response() if removal_first else self.remove_response()).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(self.run_in_connection, first)
            self.assertTrue(held.wait(5))
            second_future = pool.submit(self.run_in_connection, second)
            try:
                self.assertTrue(attempted.wait(5))
                # The old Team -> User publisher would hold Team here and then
                # deadlock as the real remover resumes with User -> Team.
                self.wait_for_postgres_lock(pids['second'])
            finally:
                release.set()
            self.assertEqual(first_future.result(timeout=10), 200)
            self.assertEqual(second_future.result(timeout=10), 409 if removal_first else 200)
        self.team.refresh_from_db()
        self.assertFalse(Membership.objects.filter(team=self.team, user=self.student).exists())
        notifications = Record.objects.filter(collection='notifications', team=self.team)
        if removal_first:
            self.assertEqual(notifications.count(), 0)
            self.assertEqual(MailJob.objects.count(), 0)
            self.assertEqual(self.team.payload['messages'][0]['status'], 'draft')
        else:
            self.assertEqual(notifications.count(), 1)
            self.assertEqual(self.team.payload['messages'][0]['status'], 'published')
            self.assertEqual(MailJob.objects.filter(kind='learning').count(), 1)
            from .mail import process_mail
            process_mail()
            self.assertEqual(MailJob.objects.get(kind='learning').status, 'cancelled')

    def test_member_removal_user_lock_then_publish_does_not_take_reverse_team_lock(self):
        self.publish_remove_race(removal_first=True)

    def test_publish_user_lock_then_member_removal_keeps_notification_and_cancels_mail(self):
        self.publish_remove_race(removal_first=False)

    def test_publish_queue_does_not_upgrade_user_lock_against_foreign_key_checks(self):
        # Django PostgreSQL FKs are deferred. Force the real FK check now so its
        # KEY SHARE lock models an in-flight submission/audit deterministically.
        held, attempt_team, queue_entered = threading.Event(), threading.Event(), threading.Event()
        release_fk, release_queue = threading.Event(), threading.Event()
        pids = {}
        fixture_id = 'fk_fixture_' + uuid.uuid4().hex

        def foreign_key_writer():
            with transaction.atomic():
                Audit.objects.create(actor=self.student, action='isolated-fk-order-fixture')
                with connection.cursor() as cursor:
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                self.worker_pid(pids, 'writer')
                held.set()
                if not release_fk.wait(8):
                    raise AssertionError('Fixture foreign-key release timed out')
                attempt_team.set()
                Record.objects.create(id=fixture_id, collection='projects', owner=self.student, team=self.team, payload={'id': fixture_id, 'title': '独立FK锁样例'})
            return 'created'

        from .views import queue_learning as real_queue_learning

        def paused_real_queue(*args, **kwargs):
            queue_entered.set()
            if not release_queue.wait(8):
                raise AssertionError('Fixture queue release timed out')
            return real_queue_learning(*args, **kwargs)

        with patch('platform_app.views.queue_learning', side_effect=paused_real_queue):
            with ThreadPoolExecutor(max_workers=2) as pool:
                writer = pool.submit(self.run_in_connection, foreign_key_writer)
                self.assertTrue(held.wait(5))
                publisher = pool.submit(self.run_in_connection, lambda: self.publish_response().status_code)
                try:
                    # NO KEY UPDATE permits this real FK KEY SHARE. FOR UPDATE
                    # would block before the publisher can even reach its queue.
                    self.assertTrue(queue_entered.wait(5))
                    release_fk.set()
                    self.assertTrue(attempt_team.wait(5))
                    self.wait_for_postgres_lock(pids['writer'])
                finally:
                    release_fk.set()
                    release_queue.set()
                self.assertEqual(publisher.result(timeout=10), 200)
                self.assertEqual(writer.result(timeout=10), 'created')
        self.assertTrue(Record.objects.filter(pk=fixture_id).exists())
        self.assertEqual(MailJob.objects.filter(kind='learning').count(), 1)
