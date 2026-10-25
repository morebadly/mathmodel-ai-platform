import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager
from django.db.models.functions import Lower

class UserManager(BaseUserManager):
    def create_user(self,email,password=None,**extra):
        user=self.model(email=self.normalize_email(email).lower(),**extra)
        user.set_password(password);user.save(using=self._db);return user
    def create_superuser(self,email,password=None,**extra):
        from .access import ADMIN_EMAILS
        alias=next((alias for alias,address in ADMIN_EMAILS.items() if address==email.lower()),None)
        if not alias:raise ValueError('管理员仅使用 admin01、admin02、admin03；请运行 provision_access 初始化。')
        extra.update(is_staff=True,is_superuser=True,role='admin',admin_login=alias)
        user=self.create_user(email,password,**extra)
        from allauth.account.models import EmailAddress
        EmailAddress.objects.update_or_create(user=user,email=user.email,defaults={'verified':True,'primary':True})
        return user

class User(AbstractUser):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    username=None
    email=models.EmailField(unique=True)
    display_name=models.CharField(max_length=120,blank=True)
    role=models.CharField(max_length=10,choices=[('student','学生'),('mentor','导师'),('admin','建设者')],default='student')
    requested_role=models.CharField(max_length=10,default='student')
    admin_login=models.CharField(max_length=7,null=True,blank=True,unique=True,choices=[('admin01','admin01'),('admin02','admin02'),('admin03','admin03')])
    cohort=models.CharField(max_length=120,blank=True)
    reminder_consent=models.BooleanField(default=False)
    track_usage=models.BooleanField(default=True)
    USERNAME_FIELD='email'
    REQUIRED_FIELDS=[]
    objects=UserManager()
    class Meta:
        constraints=[models.UniqueConstraint(Lower('email'),name='user_email_lower_unique'),models.CheckConstraint(condition=models.Q(admin_login__isnull=True)|models.Q(admin_login__in=['admin01','admin02','admin03'],role='admin',is_staff=True,is_superuser=True),name='fixed_admin_identity')]

class RegistrationPolicy(models.Model):
    id=models.CharField(primary_key=True,max_length=12,default='default',editable=False)
    mentor_key_hash=models.CharField(max_length=128)
    updated_at=models.DateTimeField(auto_now=True)

class EmailCode(models.Model):
    """One current, bounded OTP per account and purpose; no plaintext code here."""
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    purpose=models.CharField(max_length=8,choices=[('verify','邮箱验证'),('reset','重置密码')])
    nonce=models.UUIDField(default=uuid.uuid4)
    code_hash=models.CharField(max_length=64)
    requested_role=models.CharField(max_length=10,default='student')
    expires_at=models.DateTimeField()
    sent_at=models.DateTimeField()
    attempts=models.PositiveSmallIntegerField(default=0)
    used_at=models.DateTimeField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['user','purpose'],name='account_email_code_purpose_unique')]

class ChatRoom(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    key=models.CharField(max_length=220,unique=True)
    title=models.CharField(max_length=160)
    team=models.OneToOneField('Record',null=True,blank=True,on_delete=models.CASCADE,related_name='chat_room')
    created_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='created_chat_rooms')
    updated_at=models.DateTimeField(auto_now=True)

class ChatParticipant(models.Model):
    room=models.ForeignKey(ChatRoom,on_delete=models.CASCADE,related_name='participants')
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='chat_participations')
    last_read=models.PositiveBigIntegerField(default=0)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['room','user'],name='chat_room_participant_unique')]

class ChatMessage(models.Model):
    id=models.BigAutoField(primary_key=True)
    room=models.ForeignKey(ChatRoom,on_delete=models.CASCADE,related_name='messages')
    sender=models.ForeignKey(User,on_delete=models.PROTECT)
    client_id=models.UUIDField()
    body=models.TextField(blank=True)
    attachments=models.JSONField(default=list)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['room','sender','client_id'],name='chat_message_idempotency')]
        indexes=[models.Index(fields=['room','id'])]

class ExecutionJob(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(User,on_delete=models.CASCADE)
    client_id=models.UUIDField()
    provider=models.CharField(max_length=24)
    runtime=models.CharField(max_length=32)
    code=models.TextField()
    input_ids=models.JSONField(default=list)
    limits=models.JSONField(default=dict)
    status=models.CharField(max_length=32,default='queued',db_index=True)
    remote_id=models.CharField(max_length=200,blank=True)
    logs=models.TextField(blank=True)
    error=models.CharField(max_length=500,blank=True)
    cleanup_pending=models.BooleanField(default=False)
    attempts=models.PositiveIntegerField(default=0)
    claimed_at=models.DateTimeField(null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['owner','client_id'],name='execution_client_unique')]

class ExecutionArtifact(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    job=models.ForeignKey(ExecutionJob,on_delete=models.CASCADE,related_name='artifacts')
    name=models.CharField(max_length=200)
    file=models.FileField(upload_to='execution-results/%Y/%m/')
    size=models.PositiveIntegerField()
    mime=models.CharField(max_length=100,default='application/octet-stream')
    sha256=models.CharField(max_length=64)

class IndexTask(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(User,on_delete=models.CASCADE)
    provider=models.CharField(max_length=24,default='keyword')
    action=models.CharField(max_length=16)
    resource_ids=models.JSONField(default=list)
    status=models.CharField(max_length=32,default='queued',db_index=True)
    error=models.CharField(max_length=500,blank=True)
    processed=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

class SearchChunk(models.Model):
    resource=models.ForeignKey('Record',on_delete=models.CASCADE,related_name='search_chunks')
    revision=models.PositiveIntegerField()
    start=models.PositiveIntegerField()
    end=models.PositiveIntegerField()
    text=models.TextField()
    sha256=models.CharField(max_length=64)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['resource','start'],name='resource_chunk_offset_unique')]

class Record(models.Model):
    id=models.CharField(primary_key=True,max_length=100)
    collection=models.CharField(max_length=32,db_index=True)
    owner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='records')
    team=models.ForeignKey('self',null=True,blank=True,on_delete=models.SET_NULL,related_name='team_records')
    scope=models.CharField(max_length=12,default='private')
    payload=models.JSONField(default=dict)
    revision=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        indexes=[models.Index(fields=['collection','owner'])]

class Membership(models.Model):
    team=models.ForeignKey(Record,on_delete=models.CASCADE,related_name='memberships')
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='memberships')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['team','user'],name='team_user_unique')]

class Invitation(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    team=models.ForeignKey(Record,on_delete=models.CASCADE)
    email=models.EmailField()
    created_at=models.DateTimeField(auto_now_add=True)
    accepted_at=models.DateTimeField(null=True)
    version=models.PositiveIntegerField(default=1)
    issued_at=models.DateTimeField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['team','email'],name='team_invite_email_unique')]

class Asset(models.Model):
    record=models.OneToOneField(Record,on_delete=models.CASCADE,primary_key=True)
    file=models.FileField(upload_to='originals/%Y/%m/')
    original_name=models.CharField(max_length=240)
    size=models.PositiveBigIntegerField()
    sha256=models.CharField(max_length=64)
    content_type=models.CharField(max_length=160,blank=True)
    parse_status=models.CharField(max_length=20,default='pending')
    parse_error=models.CharField(max_length=400,blank=True)
    claimed_at=models.DateTimeField(null=True)

class Workspace(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE,primary_key=True)
    preferences=models.JSONField(default=dict)

class Usage(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    started_at=models.DateTimeField()
    ended_at=models.DateTimeField()
    day=models.DateField()
    activity=models.CharField(max_length=12,default='learning')
    modules=models.JSONField(default=list)
    class Meta:
        indexes=[models.Index(fields=['user','day'])]

class MailJob(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(User,null=True,on_delete=models.SET_NULL,related_name='mail_jobs')
    recipient=models.EmailField()
    kind=models.CharField(max_length=20,default='auth')
    subject=models.CharField(max_length=240)
    body=models.TextField()
    dedup_key=models.CharField(max_length=240,unique=True)
    status=models.CharField(max_length=20,default='queued')
    attempts=models.PositiveIntegerField(default=0)
    planned_at=models.DateTimeField()
    updated_at=models.DateTimeField(auto_now=True)
    created_at=models.DateTimeField(auto_now_add=True)
    last_error=models.CharField(max_length=400,blank=True)
    recipient_user=models.ForeignKey(User,null=True,on_delete=models.SET_NULL,related_name='received_mail_jobs')
    context=models.ForeignKey(Record,null=True,on_delete=models.SET_NULL,related_name='context_mail_jobs')
    email_code=models.ForeignKey(EmailCode,null=True,on_delete=models.SET_NULL)
    email_code_nonce=models.UUIDField(null=True)

class AIRun(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    operation=models.CharField(max_length=24)
    model=models.CharField(max_length=120)
    messages=models.JSONField(default=list)
    output=models.TextField()
    usage=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    paper=models.ForeignKey(Record,null=True,on_delete=models.SET_NULL)
    input_hash=models.CharField(max_length=64,blank=True)

class Audit(models.Model):
    actor=models.ForeignKey(User,null=True,on_delete=models.SET_NULL)
    action=models.CharField(max_length=80)
    target=models.CharField(max_length=120,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

class RuntimeStatus(models.Model):
    name=models.CharField(primary_key=True,max_length=40)
    last_seen=models.DateTimeField()
