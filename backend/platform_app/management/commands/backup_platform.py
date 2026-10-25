"""Offline portable fixture + originals. Contains private data; secrets exported separately."""
import hashlib,json,shutil,sqlite3
from contextlib import closing
from pathlib import Path
from django.conf import settings
from django.core.management import BaseCommand,CommandError,call_command
from django.apps import apps
from django.utils import timezone
from platform_app import private_storage
from platform_app.models import Asset,ExecutionJob,ExecutionArtifact

def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(1024*1024):sha.update(data)
    return sha.hexdigest()

class Command(BaseCommand):
    help='停写后导出数据库可迁移格式、全部原件与SHA清单；不导出密钥。'
    def add_arguments(self,p):p.add_argument('--destination',required=True);p.add_argument('--writers-stopped',action='store_true')
    def handle(self,*args,**o):
        if not o['writers_stopped']:raise CommandError('必须先停止 web/worker/beat 写入，再指定 --writers-stopped。')
        if Asset.objects.filter(parse_status='processing').exists() or ExecutionJob.objects.filter(status__in=['starting','running','cancel_requested']).exists():raise CommandError('存在运行中的解析或远端任务；先停止/核对，不能导出不一致状态。')
        target=Path(o['destination']).resolve();media=Path(settings.MEDIA_ROOT).resolve()
        if target.exists() or target.is_relative_to(Path(settings.DATA_DIR).resolve()):raise CommandError('目标必须是数据目录之外的新目录。')
        expected={}
        for model in [Asset,ExecutionArtifact]:
            for item in model.objects.all():
                path=Path(item.file.path).resolve()
                if not path.is_relative_to(media) or not path.is_file() or path.stat().st_size!=item.size or digest(path)!=item.sha256:raise CommandError('原件引用、大小或SHA核验失败，拒绝生成成功备份。')
                expected[path.relative_to(media).as_posix()]=(item.size,item.sha256)
        private_storage.protect_private_directory(target);fixture=target/'database.json'
        with fixture.open('w',encoding='utf-8') as stream:
            call_command('dumpdata',format='fulljson',natural_foreign=True,natural_primary=False,exclude=['contenttypes','auth.Permission','sessions','django_celery_beat'],stdout=stream,verbosity=0)
        private_storage.protect_private_file(fixture)
        files=[]
        if media.exists():
            for source in sorted(media.rglob('*')):
                if source.is_symlink() or source.is_junction() or not source.resolve().is_relative_to(media):raise CommandError('拒绝打包指向原件目录之外的链接。')
                if not source.is_file():continue
                relative=source.relative_to(media);destination=target/'files'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,destination);size=destination.stat().st_size;sha=digest(destination)
                if relative.as_posix() in expected and expected[relative.as_posix()]!=(size,sha):raise CommandError('原件复制期间发生变化，备份未完成。')
                files.append({'path':relative.as_posix(),'size':size,'sha256':sha})
        counts={m._meta.label:m.objects.count() for m in apps.get_app_config('platform_app').get_models()}
        identities={m._meta.label:hashlib.sha256(json.dumps(sorted(str(pk) for pk in m.objects.values_list('pk',flat=True))).encode()).hexdigest() for m in apps.get_app_config('platform_app').get_models()}
        manifest={'format':'mathmodel-offline-migration','version':1,'createdAt':timezone.now().isoformat(),'databaseSha256':digest(fixture),'files':files,'counts':counts,'identities':identities,'secretsIncluded':False,'sessionsIncluded':False,'notes':'Keep django-secret and private-access handoff separately. Stop writers for consistency.'}
        (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8');private_storage.protect_private_file(target/'manifest.json')
        if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
            with closing(sqlite3.connect(settings.DATABASES['default']['NAME'])) as source,closing(sqlite3.connect(target/'source.sqlite3')) as dest:source.backup(dest)
            private_storage.protect_private_file(target/'source.sqlite3')
        self.stdout.write(f'备份完成：{len(files)}个文件；迁移包含私有数据，请受控保管。')
