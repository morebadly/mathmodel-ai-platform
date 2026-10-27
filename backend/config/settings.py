from pathlib import Path
import os
import secrets
import hashlib
from urllib.parse import urlsplit
from dotenv import load_dotenv
from config.origins import additional_https_origins

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / '.env.local', override=False)
# Deployment secrets are mounted separately, never baked into the image or frontend.
for secret_name in ['DJANGO_SECRET_KEY','POSTGRES_PASSWORD','EMAIL_HOST_PASSWORD','AI_API_KEY','E2B_API_KEY','RUNNER_API_KEY']:
    secret_path=os.getenv(secret_name+'_FILE')
    if secret_path:
        os.environ[secret_name]=Path(secret_path).read_text('utf-8').strip()
DEBUG = os.getenv('MATHMODEL_DEBUG', '1') == '1'
DATA_DIR = Path(os.getenv('MATHMODEL_DATA_DIR', str(BASE_DIR / '.data'))).resolve()
INSTANCE_KIND=os.getenv('MATHMODEL_INSTANCE_KIND','local' if DEBUG else 'production')
if INSTANCE_KIND not in ['local','test','production']:raise RuntimeError('平台环境类型无效。')
if INSTANCE_KIND=='test' and (not DEBUG or DATA_DIR==(BASE_DIR/'.data').resolve()):
    raise RuntimeError('验收环境必须使用独立的 MATHMODEL_DATA_DIR，禁止连接日常资料目录。')
DATA_DIR.mkdir(parents=True, exist_ok=True)
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('生产环境必须配置 DJANGO_SECRET_KEY。')
    secret_file = DATA_DIR / 'django-secret'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(64), encoding='utf-8')
    SECRET_KEY = secret_file.read_text(encoding='utf-8').strip()
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',')
SITE_URL = os.getenv('MATHMODEL_SITE_URL', 'http://127.0.0.1:8765').rstrip('/')
ADDITIONAL_HTTPS_ORIGINS=additional_https_origins(os.getenv('MATHMODEL_ADDITIONAL_HTTPS_ORIGINS',''),ALLOWED_HOSTS)
CHAT_ALLOWED_ORIGINS = list(dict.fromkeys([SITE_URL,*ADDITIONAL_HTTPS_ORIGINS]))
if os.getenv('MATHMODEL_QA_LOOPBACK_SESSIONS','0') == '1':
    qa_site=urlsplit(SITE_URL)
    if not DEBUG or INSTANCE_KIND!='test' or qa_site.scheme!='http' or qa_site.hostname not in ['127.0.0.1','localhost'] or not qa_site.port:
        raise RuntimeError('独立浏览器验收仅允许测试环境的明确回环端口。')
    CHAT_ALLOWED_ORIGINS = [f'http://127.0.0.1:{qa_site.port}', f'http://localhost:{qa_site.port}']
INSTANCE_LABEL=os.getenv('MATHMODEL_INSTANCE_LABEL') or {'local':'本地平台','test':'功能验收环境','production':'正式平台'}[INSTANCE_KIND]
INSTANCE_PRIMARY_URL=os.getenv('MATHMODEL_PRIMARY_URL','').rstrip('/') if DEBUG and INSTANCE_KIND=='test' else ''
if INSTANCE_PRIMARY_URL:
    primary=urlsplit(INSTANCE_PRIMARY_URL)
    if primary.scheme not in ['http','https'] or primary.hostname not in ['localhost','127.0.0.1','::1'] or primary.username or primary.password or primary.path not in ['','/'] or primary.query or primary.fragment:raise RuntimeError('本机原资料入口必须是回环地址。')
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','django.contrib.sites','rest_framework','allauth','allauth.account','allauth.headless','django_celery_beat','platform_app']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','platform_app.middleware.AccountBindingMiddleware','allauth.account.middleware.AccountMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
if os.getenv('POSTGRES_DB'):
    DATABASES = {'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.environ['POSTGRES_DB'],'USER':os.environ['POSTGRES_USER'],'PASSWORD':os.environ['POSTGRES_PASSWORD'],'HOST':os.getenv('POSTGRES_HOST','127.0.0.1'),'PORT':os.getenv('POSTGRES_PORT','5432')}}
else:
    DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':DATA_DIR/'platform.sqlite3','OPTIONS':{'timeout':30,'transaction_mode':'IMMEDIATE'}}}
AUTH_USER_MODEL = 'platform_app.User'
AUTHENTICATION_BACKENDS = ['platform_app.backends.FixedAdminBackend','django.contrib.auth.backends.ModelBackend','allauth.account.auth_backends.AuthenticationBackend']
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*','password1*','password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_ADAPTER = 'platform_app.adapters.AccountAdapter'
SITE_ID = 1
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SERIALIZATION_MODULES={'fulljson':'platform_app.migration_serializer'}
MEDIA_ROOT = DATA_DIR/'files'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR/'backend'/'staticfiles'
EMAIL_BACKEND = 'platform_app.mail.QueueEmailBackend'
MAIL_TRANSPORT = os.getenv('MAIL_TRANSPORT','local')
ALLOW_DEV_MAILBOX = DEBUG and MAIL_TRANSPORT == 'local'
QA_ADMIN_MAILBOX = DEBUG and INSTANCE_KIND == 'test' and os.getenv('MATHMODEL_QA_ADMIN_MAILBOX','0') == '1'
if not DEBUG and MAIL_TRANSPORT == 'local':
    raise RuntimeError('生产环境禁止启用本地开发邮件箱。')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL','MathModel AI <dev@example.invalid>')
EMAIL_HOST = os.getenv('EMAIL_HOST','')
EMAIL_PORT = int(os.getenv('EMAIL_PORT','587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS','1') == '1'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL','0') == '1'
EMAIL_PROXY_URL = os.getenv('EMAIL_PROXY_URL','')
EMAIL_TIMEOUT = 20
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME=os.getenv('MATHMODEL_SESSION_COOKIE_NAME') or ('sessionid' if not DEBUG or DATA_DIR==BASE_DIR/'.data' else 'mathmodel_session_'+hashlib.sha256(os.path.normcase(str(DATA_DIR)).encode()).hexdigest()[:12])
if INSTANCE_KIND=='test' and SESSION_COOKIE_NAME=='sessionid':
    raise RuntimeError('验收环境禁止共用日常账号的 sessionid cookie。')
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN' if DEBUG else 'DENY'
PASSWORD_RESET_TIMEOUT = 1800
DATA_UPLOAD_MAX_MEMORY_SIZE = 32*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2*1024*1024
MAX_FILE_BYTES = 50*1024*1024
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'EXCEPTION_HANDLER':'platform_app.views.api_exception','DEFAULT_THROTTLE_CLASSES':['rest_framework.throttling.UserRateThrottle','rest_framework.throttling.AnonRateThrottle'],'DEFAULT_THROTTLE_RATES':{'user':'600/min','anon':'120/min'}}
REST_FRAMEWORK['DEFAULT_PARSER_CLASSES']=['platform_app.parsers.ObjectJSONParser','rest_framework.parsers.FormParser','rest_framework.parsers.MultiPartParser']
REDIS_URL = os.getenv('REDIS_URL','')
CHANNEL_LAYERS={'default':{'BACKEND':'channels_redis.core.RedisChannelLayer','CONFIG':{'hosts':[REDIS_URL],'capacity':500,'expiry':60}}} if REDIS_URL else {'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}}
if REDIS_URL:
    CACHES={'default':{'BACKEND':'django.core.cache.backends.redis.RedisCache','LOCATION':REDIS_URL}}
CELERY_BROKER_URL = REDIS_URL or 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {'platform-maintenance':{'task':'platform_app.tasks.maintenance','schedule':30.0}}
CELERY_TASK_TIME_LIMIT = 180
CELERY_TASK_SOFT_TIME_LIMIT = 150
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 384000
AI_BASE_URL = os.getenv('AI_BASE_URL','https://api.deepseek.com').rstrip('/')
AI_MODEL = os.getenv('AI_MODEL','deepseek-flash')
AI_API_KEY = os.getenv('AI_API_KEY','')
AI_ALLOW_LOCAL = DEBUG and os.getenv('AI_ALLOW_LOCAL','0') == '1'
AI_MAX_OUTPUT_TOKENS = int(os.getenv('AI_MAX_OUTPUT_TOKENS','2048'))
AI_MAX_INPUT_CHARS = int(os.getenv('AI_MAX_INPUT_CHARS','30000'))
AI_DAILY_REQUESTS = int(os.getenv('AI_DAILY_REQUESTS','20'))
AI_GLOBAL_DAILY_REQUESTS = int(os.getenv('AI_GLOBAL_DAILY_REQUESTS','100'))
AI_CONCURRENCY = int(os.getenv('AI_CONCURRENCY','2'))
if not (128 <= AI_MAX_OUTPUT_TOKENS <= 8192 and 100 <= AI_MAX_INPUT_CHARS <= 150000 and 1 <= AI_CONCURRENCY <= 8 and AI_DAILY_REQUESTS > 0 and AI_GLOBAL_DAILY_REQUESTS > 0):
    raise RuntimeError('模型调用限制配置无效。')
MEDIA_MODEL_DIR=Path(os.getenv('MEDIA_MODEL_DIR',str(BASE_DIR/'.runtime/models'))).resolve()
FFMPEG_PATH=os.getenv('FFMPEG_PATH','ffmpeg')
MEDIA_TASK_TIMEOUT=int(os.getenv('MEDIA_TASK_TIMEOUT','180'))
SANDBOX_PROVIDER=os.getenv('SANDBOX_PROVIDER','e2b')
E2B_API_KEY=os.getenv('E2B_API_KEY','')
E2B_TEMPLATE=os.getenv('E2B_TEMPLATE','')
RUNNER_URL=os.getenv('RUNNER_URL','').rstrip('/')
RUNNER_API_KEY=os.getenv('RUNNER_API_KEY','')
RUNTIME_AUTHORIZATION={name:os.getenv(name.upper()+'_AUTHORIZED','0')=='1' for name in ['matlab','gurobi','cplex']}
SANDBOX_MAX_SECONDS=int(os.getenv('SANDBOX_MAX_SECONDS','120'))
SANDBOX_INPUT_BYTES=int(os.getenv('SANDBOX_INPUT_BYTES',str(10*1024*1024)))
SANDBOX_OUTPUT_BYTES=int(os.getenv('SANDBOX_OUTPUT_BYTES',str(10*1024*1024)))
SANDBOX_CPUS=int(os.getenv('SANDBOX_CPUS','2'))
SANDBOX_MEMORY_MB=int(os.getenv('SANDBOX_MEMORY_MB','4096'))
SANDBOX_CONCURRENCY=int(os.getenv('SANDBOX_CONCURRENCY','2'))
SANDBOX_DAILY_JOBS=int(os.getenv('SANDBOX_DAILY_JOBS','20'))
if SANDBOX_PROVIDER not in ['e2b','gateway']:raise RuntimeError('SANDBOX_PROVIDER must be e2b or gateway.')
CELERY_TASK_ROUTES={'platform_app.tasks.media_tick':{'queue':'media'},'platform_app.tasks.execution_tick':{'queue':'execution'}}
CELERY_BEAT_SCHEDULE.update({'media-tick':{'task':'platform_app.tasks.media_tick','schedule':10.0},'execution-tick':{'task':'platform_app.tasks.execution_tick','schedule':5.0}})
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([SITE_URL,*ADDITIONAL_HTTPS_ORIGINS])) if not DEBUG else []
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS=os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS','0')=='1'
SECURE_HSTS_PRELOAD=os.getenv('SECURE_HSTS_PRELOAD','0')=='1'
if os.getenv('TRUST_HTTPS_PROXY','0')=='1':SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SECURE_REDIRECT_EXEMPT=[r'^health(?:/ready)?$']
if not DEBUG and not SITE_URL.startswith('https://'):raise RuntimeError('生产环境 SITE_URL 必须使用 HTTPS。')
LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},'loggers':{'django':{'handlers':['console'],'level':'WARNING','propagate':False},'platform_app':{'handlers':['console'],'level':'INFO','propagate':False}}}
if MAIL_TRANSPORT not in ['local','smtp']:raise RuntimeError('MAIL_TRANSPORT 仅支持 local / smtp。')
if EMAIL_USE_TLS and EMAIL_USE_SSL:raise RuntimeError('SMTP TLS 与 SSL 不能同时开启。')
if not DEBUG and (not os.getenv('POSTGRES_DB') or not REDIS_URL):raise RuntimeError('生产环境必须配置 PostgreSQL 与 Redis。')
