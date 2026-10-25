"""Start the approved Django backend and local development mail/job worker."""
import argparse
import os
from pathlib import Path
import threading
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=8765)
parser.add_argument('--no-jobs',action='store_true')
parser.add_argument('--test-instance',action='store_true',help='明确标识独立验收环境。')
parser.add_argument('--primary-url',default='',help='验收环境中显示的原资料平台回环地址。')
args=parser.parse_args()
os.environ.setdefault('MATHMODEL_SITE_URL',f'http://127.0.0.1:{args.port}')
if args.test_instance:os.environ['MATHMODEL_INSTANCE_KIND']='test'
if args.primary_url:os.environ['MATHMODEL_PRIMARY_URL']=args.primary_url
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
import uvicorn
if not settings.DEBUG:raise RuntimeError('此启动器仅供本机联调；生产环境请使用部署说明。')
call_command('check')
call_command('migrate',interactive=False,verbosity=0)
call_command('provision_access',verbosity=0)
worker=None
stop=threading.Event()
def local_jobs():
    from platform_app.tasks import maintenance
    while not stop.is_set():
        try:maintenance.run()
        except Exception as error:print('Local job cycle failed: '+type(error).__name__,flush=True)
        stop.wait(5)
def queue_loop(task_name):
    from platform_app import tasks
    while not stop.is_set():
        try:getattr(tasks,task_name).run()
        except Exception as error:print('Local '+task_name+' cycle failed: '+type(error).__name__,flush=True)
        stop.wait(3)
try:
    if not args.no_jobs:
        worker=threading.Thread(target=local_jobs,name='mathmodel-local-jobs',daemon=True);worker.start()
        for name in ['media_tick','execution_tick']:
            threading.Thread(target=queue_loop,args=(name,),name='mathmodel-'+name,daemon=True).start()
    print(f'MathModel AI Django: http://127.0.0.1:{args.port}/',flush=True)
    print(f'Local development mailbox: http://127.0.0.1:{args.port}/dev-mailbox/ (no external mail)',flush=True)
    uvicorn.run('config.asgi:application',host='127.0.0.1',port=args.port,access_log=False,ws_max_size=64*1024,timeout_keep_alive=15)
finally:
    stop.set()
