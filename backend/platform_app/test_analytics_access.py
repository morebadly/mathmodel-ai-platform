"""Workspace analytics authorization; all rows below are isolated test fixtures."""
import json
from datetime import datetime, timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .access import ADMIN_EMAILS
from .models import Membership, Record, Usage, User
from .tests import Client, key, person, project as make_project, record


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AnalyticsAccessTests(TestCase):
    client_class = Client

    def setUp(self):
        cache.clear()
        self.admin = person('admin', 'admin')
        self.mentor = person('mentor', 'mentor')
        self.other_mentor = person('other-mentor', 'mentor')
        self.student = person('student')
        self.peer = person('peer')
        self.other = person('other-team-student')
        self.unassigned = person('unassigned-student')
        self.students = [self.student, self.peer, self.other, self.unassigned]
        self.team = record(self.mentor, 'teams', name='Authorized team')
        for student in [self.student, self.peer]:
            Membership.objects.create(team=self.team, user=student)
        other_team = record(self.other_mentor, 'teams', name='Other team')
        Membership.objects.create(team=other_team, user=self.other)

        self.started = timezone.make_aware(datetime(2026, 10, 20, 9))
        self.usage = {}
        self.scores = {}
        for index, student in enumerate(self.students):
            self.usage[str(student.id)] = [self.make_usage(student, self.started)]
            self.scores[str(student.id)] = record(
                self.admin, 'scoreRecords', personId=str(student.id),
                assessment='Isolated fixture assessment',
                assessmentDate=self.started.isoformat(),
                score=70 + index, maxScore=100,
                source='Isolated test fixture; not real school data',
            )
        self.usage[str(self.student.id)] += [
            self.make_usage(self.student, self.started + timedelta(hours=2)),
            self.make_usage(self.student, self.started + timedelta(days=1)),
        ]

    def make_usage(self, student, started):
        return Usage.objects.create(
            user=student, started_at=started,
            ended_at=started + timedelta(minutes=1),
            day=timezone.localdate(started), activity='training',
            modules=['建模训练'],
        )

    def workspace(self, user, **query):
        self.client.force_login(user, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.get('/api/workspace', query)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def assert_student_scope(self, state, students):
        allowed = {str(student.id) for student in students}
        self.assertEqual(
            {row['id'] for row in state['participants'] if row['accountRole'] == 'student'},
            allowed,
        )
        self.assertEqual({row['personId'] for row in state['scoreRecords']}, allowed)
        self.assertEqual({row['personId'] for row in state['usageRecords']}, allowed)
        self.assertEqual(
            {row['id'] for row in state['usageRecords']},
            {str(row.id) for student_id in allowed for row in self.usage[student_id]},
        )

    def create_mentor_analytics(self):
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        changes = {
            'scoreRecords': [{
                'id': key(), 'personId': str(self.student.id),
                'assessment': 'Mentor-owned isolated assessment',
                'assessmentDate': self.started.isoformat(), 'score': 82, 'maxScore': 100,
                'source': 'Isolated mentor-entered score fixture',
            }],
            'usageRecords': [{
                'id': key(), 'personId': str(self.student.id),
                'startedAt': self.started.isoformat(),
                'endedAt': (self.started + timedelta(minutes=1)).isoformat(),
                'activity': 'training', 'module': '建模训练',
                'source': 'Isolated mentor-entered usage fixture',
            }],
        }
        response = self.client.patch(
            '/api/workspace', json.dumps({'changes': changes}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        return changes

    def create_school_submission(self, mentor, student):
        task = record(mentor, 'tasks', title='School assessment', audience='school', attachmentIds=[])
        task.scope = 'school'
        task.save()
        project = make_project(student, task)
        submission_id = key()
        self.client.force_login(student, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.patch('/api/workspace', json.dumps({'changes': {
            'taskSubmissions': [{'id': submission_id, 'taskId': task.id, 'projectId': project.id}],
        }}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return task, Record.objects.get(id=submission_id)

    def submission_score(self, submission_id, student):
        return {
            'id': key(), 'personId': str(student.id), 'submissionId': submission_id,
            'assessment': 'School task assessment', 'assessmentDate': self.started.isoformat(),
            'score': 82, 'maxScore': 100, 'source': 'Isolated submission assessment fixture',
        }

    def test_disabled_account_keeps_mailbox_proof_without_access(self):
        from .domain import verified
        from .tests import PASSWORD
        self.student.is_active = False
        self.student.save(update_fields=['is_active'])
        state = self.workspace(self.admin)
        row = next(row for row in state['participants'] if row['id'] == str(self.student.id))
        self.assertTrue(row['emailVerified'])
        self.assertFalse(row['isActive'])
        self.assertFalse(verified(self.student))
        # Both an existing session and a password sign-in remain denied.
        self.client.force_login(self.student, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/workspace').status_code, 409)
        self.client.defaults.pop('HTTP_X_MM_ACCOUNT', None)
        self.assertEqual(self.client.get('/api/workspace').status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post('/api/auth/login', json.dumps({
            'email': self.student.email, 'password': PASSWORD,
        }), content_type='application/json').status_code, 401)

    def test_all_three_fixed_admins_receive_platform_usage_and_actual_scores(self):
        admins = [self.admin] + [
            User.objects.create_superuser(ADMIN_EMAILS[alias], 'Only-test-password-294!')
            for alias in ['admin02', 'admin03']
        ]
        for admin in admins:
            with self.subTest(admin=admin.admin_login):
                state = self.workspace(admin)
                self.assert_student_scope(state, self.students)
                for row in state['scoreRecords']:
                    expected = self.scores[row['personId']].payload
                    for field in ['assessment', 'assessmentDate', 'score', 'maxScore', 'source']:
                        self.assertEqual(row[field], expected[field])
                sessions = [row for row in state['usageRecords'] if row['personId'] == str(self.student.id)]
                self.assertEqual(len(sessions), 3)
                self.assertEqual(len({timezone.localdate(datetime.fromisoformat(row['startedAt'])) for row in sessions}), 2)
                self.assertTrue(all(row['capture'] == 'server' and row['_managed'] for row in sessions))

    def test_mentor_only_receives_authorized_team_even_with_forged_query(self):
        state = self.workspace(self.mentor, role='admin', personId=str(self.other.id))
        self.assert_student_scope(state, [self.student, self.peer])
        self.assertEqual(
            {row['id'] for row in state['participants']},
            {str(user.id) for user in [self.mentor, self.student, self.peer]},
        )

    def test_student_cannot_receive_same_team_peer_or_other_team_data(self):
        state = self.workspace(self.student, role='admin', personId=str(self.peer.id))
        self.assert_student_scope(state, [self.student])
        self.assertEqual([row['id'] for row in state['participants']], [str(self.student.id)])

    def test_removing_membership_revokes_mentor_analytics_for_that_student(self):
        self.assert_student_scope(self.workspace(self.mentor), [self.student, self.peer])
        Membership.objects.filter(team=self.team, user=self.student).delete()
        self.assert_student_scope(self.workspace(self.mentor), [self.peer])
        self.assert_student_scope(self.workspace(self.admin), self.students)

    def test_mentor_owned_analytics_disappear_after_membership_removal(self):
        changes = self.create_mentor_analytics()
        before = self.workspace(self.mentor)
        for collection, rows in changes.items():
            self.assertIn(rows[0]['id'], {row['id'] for row in before[collection]})
        Membership.objects.filter(team=self.team, user=self.student).delete()
        after = self.workspace(self.mentor)
        for collection, rows in changes.items():
            self.assertNotIn(rows[0]['id'], {row['id'] for row in after[collection]})
            for user in [self.student, self.admin]:
                self.assertIn(rows[0]['id'], {row['id'] for row in self.workspace(user)[collection]})

    def test_former_mentor_cannot_resave_owned_student_analytics(self):
        changes = self.create_mentor_analytics()
        Membership.objects.filter(team=self.team, user=self.student).delete()
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        for collection, rows in changes.items():
            for unchanged in [True, False]:
                with self.subTest(collection=collection, unchanged=unchanged):
                    data = dict(rows[0], _revision=1)
                    if not unchanged:
                        data['source'] = 'Unauthorized changed source'
                    response = self.client.patch(
                        '/api/workspace', json.dumps({'changes': {collection: [data]}}),
                        content_type='application/json',
                    )
                    self.assertEqual(response.status_code, 403)

    def test_mentor_keeps_private_owned_project_and_resource_access(self):
        project = record(self.mentor, 'projects', title='Private mentor project')
        resource = record(self.mentor, 'resources', name='Private mentor resource')
        Membership.objects.filter(team=self.team, user=self.student).delete()
        state = self.workspace(self.mentor)
        self.assertIn(project.id, {row['id'] for row in state['projects']})
        self.assertIn(resource.id, {row['id'] for row in state['resources']})

    def test_school_task_reviewer_can_read_and_edit_nonteam_submission_score(self):
        task, submission = self.create_school_submission(self.mentor, self.unassigned)
        score = self.submission_score(submission.id, self.unassigned)
        self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.patch('/api/workspace', json.dumps({'changes': {
            'scoreRecords': [score],
        }}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        state = self.workspace(self.mentor)
        row = next((row for row in state['scoreRecords'] if row['id'] == score['id']), None)
        self.assertIsNotNone(row)
        self.assertNotIn(str(self.unassigned.id), {row['id'] for row in state['participants']})
        self.assertNotIn(str(self.unassigned.id), {row['personId'] for row in state['usageRecords']})
        row['score'] = 90
        response = self.client.patch('/api/workspace', json.dumps({'changes': {
            'scoreRecords': [row],
        }}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Record.objects.get(id=score['id']).payload['score'], 90)
        response = self.client.patch('/api/workspace', json.dumps({'changes': {
            'usageRecords': [dict(score, id=key())],
        }}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        task.owner = self.other_mentor
        task.save()
        state = self.workspace(self.mentor)
        self.assertNotIn(score['id'], {row['id'] for row in state['scoreRecords']})
        response = self.client.patch('/api/workspace', json.dumps({'changes': {
            'scoreRecords': [row],
        }}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_fake_or_other_reviewer_submission_cannot_expand_score_access(self):
        own_task, own_submission = self.create_school_submission(self.mentor, self.other)
        _, other_submission = self.create_school_submission(self.other_mentor, self.other)
        orphan = record(self.other, 'taskSubmissions', personId=str(self.other.id), taskId=key())
        cases = [
            ('missing submission', key(), self.other),
            ('not a submission', own_task.id, self.other),
            ('mismatched person', own_submission.id, self.unassigned),
            ('other reviewer', other_submission.id, self.other),
            ('missing task', orphan.id, self.other),
        ]
        for label, submission_id, student in cases:
            with self.subTest(case=label):
                score = self.submission_score(submission_id, student)
                self.client.force_login(self.mentor, backend='django.contrib.auth.backends.ModelBackend')
                response = self.client.patch('/api/workspace', json.dumps({'changes': {
                    'scoreRecords': [score],
                }}), content_type='application/json')
                self.assertIn(response.status_code, [403, 404])
                # A malformed legacy row must not gain access through its author either.
                record(self.mentor, 'scoreRecords', **score)
                state = self.workspace(self.mentor)
                self.assertNotIn(score['id'], {row['id'] for row in state['scoreRecords']})
                response = self.client.patch('/api/workspace', json.dumps({'changes': {
                    'scoreRecords': [dict(score, _revision=1)],
                }}), content_type='application/json')
                self.assertEqual(response.status_code, 403)

    def test_absent_actual_score_is_not_fabricated(self):
        self.scores[str(self.unassigned.id)].delete()
        state = self.workspace(self.admin)
        self.assertNotIn(str(self.unassigned.id), {row['personId'] for row in state['scoreRecords']})
        self.assertIn(str(self.unassigned.id), {row['personId'] for row in state['usageRecords']})

    def test_unlisted_admin_role_cannot_read_workspace(self):
        unlisted = User.objects.create_user(
            'unlisted@example.invalid', 'Only-test-password-294!',
            role='admin', is_staff=True, is_superuser=True,
        )
        self.client.force_login(unlisted, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/workspace').status_code, 403)

    def test_anonymous_or_unverified_account_cannot_read_analytics_data(self):
        self.assertEqual(self.client.get('/api/workspace').status_code, 403)
        unverified = person('unverified-student', verified=False)
        self.client.force_login(unverified, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/workspace').status_code, 403)
