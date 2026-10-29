"""Account state changes preserve content and revoke prior sessions; isolated fixtures."""
import json
import threading
import time
import uuid
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.db import connection, connections, transaction
from unittest.mock import patch
from .models import Audit, Membership, User
from .tests import Client, PASSWORD, person, record

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountStatusTests(TestCase):
    client_class=Client

    def setUp(self):
        cache.clear()
        self.admin=person('status-admin','admin')
        self.student=person('status-student')
        self.mentor=person('status-mentor','mentor')
        self.team=record(self.mentor,'teams',name='Isolated status team')
        Membership.objects.create(team=self.team,user=self.student)
        self.content=record(self.student,'projects',title='Retain this private fixture')
        self.client.force_login(self.admin,backend='django.contrib.auth.backends.ModelBackend')

    def status(self,user,value,client=None,**extra):
        return (client or self.client).post('/api/admin/accounts/'+str(user.id)+'/status',json.dumps({'isActive':value,**extra}),content_type='application/json')

    def test_disable_and_restore_preserves_role_content_and_memberships(self):
        old=Client();old.force_login(self.student,backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(old.get('/api/workspace').status_code,200)
        self.assertEqual(self.status(self.student,False).status_code,200)
        self.student.refresh_from_db();self.assertFalse(self.student.is_active)
        self.assertEqual(self.student.role,'student')
        self.assertEqual(old.get('/api/workspace').status_code,409)
        fresh=Client()
        login={'email':self.student.email,'password':PASSWORD,'role':'student'}
        self.assertEqual(fresh.post('/api/auth/login',json.dumps(login),content_type='application/json').status_code,401)
        self.content.refresh_from_db()
        self.assertEqual(self.content.payload['title'],'Retain this private fixture')
        self.assertTrue(Membership.objects.filter(team=self.team,user=self.student).exists())
        self.assertTrue(Audit.objects.filter(action='account-disable',target=str(self.student.id)).exists())
        self.assertEqual(self.status(self.student,True).status_code,200)
        self.assertEqual(old.get('/api/workspace').status_code,409,'Re-enabling must not resurrect a revoked session')
        self.assertEqual(fresh.post('/api/auth/login',json.dumps(login),content_type='application/json').status_code,200)
        fresh.defaults['HTTP_X_MM_ACCOUNT']=str(self.student.id)
        self.assertEqual(fresh.get('/api/workspace').status_code,200)
        self.assertTrue(Audit.objects.filter(action='account-enable',target=str(self.student.id)).exists())

    def test_status_endpoint_cannot_change_role_or_accept_non_boolean(self):
        for value in ['false',0,None]:self.assertEqual(self.status(self.student,value).status_code,400)
        self.assertEqual(self.status(self.student,False,role='admin').status_code,400)
        self.student.refresh_from_db();self.assertTrue(self.student.is_active);self.assertEqual(self.student.role,'student')

    def test_only_admin_can_change_status(self):
        for actor in [self.student,self.mentor]:
            c=Client();c.force_login(actor,backend='django.contrib.auth.backends.ModelBackend')
            self.assertEqual(self.status(self.student,False,c).status_code,403)
        self.assertEqual(self.status(self.student,False,Client()).status_code,403)

    def test_fixed_admin_and_privileged_accounts_are_protected(self):
        self.assertEqual(self.status(self.admin,False).status_code,403)
        self.mentor.is_staff=True;self.mentor.save(update_fields=['is_staff'])
        self.assertEqual(self.status(self.mentor,False).status_code,403)
        self.admin.refresh_from_db();self.mentor.refresh_from_db()
        self.assertTrue(self.admin.is_active);self.assertTrue(self.mentor.is_active)

    def test_role_only_change_preserves_disabled_state(self):
        self.status(self.student,False)
        r=self.client.post('/api/admin/accounts/'+str(self.student.id)+'/role',json.dumps({'role':'mentor'}),content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.student.refresh_from_db();self.assertEqual(self.student.role,'mentor');self.assertFalse(self.student.is_active)

    def test_legacy_role_and_status_request_still_works(self):
        r=self.client.post('/api/admin/accounts/'+str(self.student.id)+'/role',json.dumps({'role':'mentor','isActive':False}),content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.student.refresh_from_db();self.assertEqual(self.student.role,'mentor');self.assertFalse(self.student.is_active)

    def test_login_authentication_is_persisted_before_releasing_account_lock(self):
        original=Audit.objects.create
        def inspect_session(**kwargs):
            if kwargs.get('action')=='login':
                self.assertTrue(any(s.get_decoded().get('_auth_user_id')==str(self.student.id) for s in Session.objects.all()))
            return original(**kwargs)
        with patch('platform_app.auth_views.Audit.objects.create',side_effect=inspect_session):
            c=Client()
            r=c.post('/api/auth/login',json.dumps({'email':self.student.email,'password':PASSWORD}),content_type='application/json')
            self.assertEqual(r.status_code,200)

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountStatusConcurrencyTests(TransactionTestCase):
    def setUp(self):
        cache.clear();self.admin=person('race-admin','admin');self.student=person('race-student')
        self.admin_client=Client();self.admin_client.force_login(self.admin,backend='django.contrib.auth.backends.ModelBackend')
        self.workers=[];self.errors=[];self.results={}

    def start(self,label,fn):
        app='account-status-'+uuid.uuid4().hex
        def work():
            try:
                connection.settings_dict=dict(connection.settings_dict,CONN_MAX_AGE=60)
                with connection.cursor() as c:c.execute("SELECT set_config('application_name',%s,false)",[app])
                self.results[label]=fn()
            except Exception as error:self.errors.append(type(error).__name__)
            finally:connections.close_all()
        thread=threading.Thread(target=work,daemon=True);self.workers.append(thread);thread.start();return app

    def wait_for_row_lock(self,app):
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            with connection.cursor() as c:
                c.execute('SELECT pg_stat_clear_snapshot()')
                c.execute('SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s',[app]);rows=c.fetchall()
            if any(row[0]=='Lock' for row in rows):return
            time.sleep(.03)
        self.fail('The competing request never waited for the account row lock')

    def finish(self):
        for worker in self.workers:worker.join(timeout=10)
        self.assertFalse(any(worker.is_alive() for worker in self.workers));self.assertEqual(self.errors,[])

    def status(self,value,client=None):
        return (client or self.admin_client).post('/api/admin/accounts/'+str(self.student.id)+'/status',json.dumps({'isActive':value}),content_type='application/json')

    def login(self,client):
        return client.post('/api/auth/login',json.dumps({'email':self.student.email,'password':PASSWORD}),content_type='application/json')

    @skipUnlessDBFeature('has_select_for_update')
    def test_login_lock_precedes_disable_and_old_cookie_stays_revoked(self):
        from . import auth_views
        entered=threading.Event();release=threading.Event();original=auth_views.login
        def paused_login(*args,**kwargs):
            entered.set()
            if not release.wait(10):raise RuntimeError('Login barrier timed out')
            return original(*args,**kwargs)
        stale=Client();disabler=Client();disabler.force_login(self.admin,backend='django.contrib.auth.backends.ModelBackend')
        with patch('platform_app.auth_views.login',side_effect=paused_login):
            try:
                self.start('login',lambda:self.login(stale))
                self.assertTrue(entered.wait(6))
                app=self.start('disable',lambda:self.status(False,disabler))
                self.wait_for_row_lock(app)
            finally:release.set();self.finish()
        self.assertIn(self.results['login'].status_code,[200,400])
        self.assertEqual(self.results['disable'].status_code,200)
        self.assertEqual(self.status(True).status_code,200)
        stale.defaults['HTTP_X_MM_ACCOUNT']=str(self.student.id)
        self.assertEqual(stale.get('/api/workspace').status_code,409)

    @skipUnlessDBFeature('has_select_for_update')
    def test_disable_lock_precedes_login_and_login_is_denied(self):
        client=Client()
        try:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=self.student.pk)
                app=self.start('login',lambda:self.login(client))
                self.wait_for_row_lock(app)
                self.assertEqual(self.status(False).status_code,200)
        finally:self.finish()
        self.assertEqual(self.results['login'].status_code,401)
