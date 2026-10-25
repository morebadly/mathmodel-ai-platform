import json
import secrets
import string
from pathlib import Path
from django.conf import settings
from django.contrib.auth.hashers import make_password,check_password
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from platform_app.models import User,RegistrationPolicy,Audit
from platform_app.access import ADMIN_LOGINS,ADMIN_EMAILS,fixed_admin
from platform_app import private_storage

def password():
    alphabet=string.ascii_letters+string.digits
    return 'Mm!'+''.join(secrets.choice(alphabet) for _ in range(18))

class Command(BaseCommand):
    help='一次性初始化统一导师密钥和三个固定管理员；重复执行不改密码。'
    def handle(self,*args,**options):
        try:
            path=private_storage.credential_path(settings.DATA_DIR)
            legacy=settings.DATA_DIR/'access-credentials.json'
            if not path.exists() and legacy.exists():
                private_storage.protect_private_file(legacy)
                # Both paths are fixed children of DATA_DIR; preserve existing credentials.
                if legacy.parent.resolve()!=settings.DATA_DIR.resolve() or path.parent.parent.resolve()!=settings.DATA_DIR.resolve():raise OSError('Invalid credential path')
                legacy.replace(path)
        except Exception:raise CommandError('无法准备私有凭据目录，未改写现有账号。')
        if path.exists():
            try:
                private_storage.protect_private_file(path)
                delivery=json.loads(path.read_text(encoding='utf-8'))
            except Exception:raise CommandError('本地凭据文件无效或无法限制其权限，未改写现有账号。')
        else:
            if RegistrationPolicy.objects.exists() or User.objects.filter(admin_login__isnull=False).exists():raise CommandError('访问策略已存在，未重置凭据；请使用现有密钥和管理员密码。')
            delivery={'mentorKey':'MM-MENTOR-'+secrets.token_hex(10).upper(),'admins':[{'account':alias,'initialPassword':password()} for alias in ADMIN_LOGINS]}
        if set(row.get('account') for row in delivery.get('admins',[]))!=set(ADMIN_LOGINS) or len(delivery['admins'])!=3 or not isinstance(delivery.get('mentorKey'),str):raise CommandError('凭据结构无效，未改写账号。')
        with transaction.atomic():
            policy=RegistrationPolicy.objects.select_for_update().filter(pk='default').first()
            if policy and not check_password(delivery['mentorKey'],policy.mentor_key_hash):raise CommandError('现有导师密钥与本地凭据不一致，未自动轮换。')
            if not policy:RegistrationPolicy.objects.create(id='default',mentor_key_hash=make_password(delivery['mentorKey']))
            for row in delivery['admins']:
                alias=row['account'];user=User.objects.filter(admin_login=alias).first()
                if user:
                    if user.role!='admin' or user.email!=ADMIN_EMAILS[alias] or not user.is_staff or not user.is_superuser:raise CommandError('固定账号配置不一致，未改写权限。')
                    continue
                if User.objects.filter(email__iexact=ADMIN_EMAILS[alias]).exists():raise CommandError('保留地址已被其他账号占用，未授予其管理员权限。')
                user=User.objects.create_user(ADMIN_EMAILS[alias],row['initialPassword'],admin_login=alias,display_name='管理员 '+alias[-2:],role='admin',requested_role='admin',is_staff=True,is_superuser=True,track_usage=False)
                Audit.objects.create(actor=user,action='fixed-admin-provision',target=alias)
            # A failed DB transaction can safely reuse this delivery file on the next run.
            if not path.exists():
                try:private_storage.write_private_json(path,delivery)
                except Exception:raise CommandError('无法安全保存本地凭据，账号初始化已撤销。')
        self.stdout.write('统一导师密钥与三个固定管理账号已就绪。凭据仅保存在：'+str(path))
