import json,shutil,tempfile,hashlib
from pathlib import Path,PurePosixPath
from django.conf import settings
from django.core.management import BaseCommand,CommandError,call_command
from django.db import transaction
from platform_app.models import User,Record,ChatMessage
from .backup_platform import digest

class Command(BaseCommand):
    help='只向已迁移但尚无业务数据的新数据库恢复迁移包；不覆盖现有平台。'
    def add_arguments(self,p):p.add_argument('--source',required=True);p.add_argument('--empty-database',action='store_true')
    def handle(self,*args,**o):
        if not o['empty_database'] or User.objects.exists() or Record.objects.exists() or ChatMessage.objects.exists():raise CommandError('仅允许显式确认的空目标库，禁止覆盖现有账号或资料。')
        root=Path(o['source']).resolve();manifest=json.loads((root/'manifest.json').read_text('utf-8'));media=Path(settings.MEDIA_ROOT).resolve()
        if manifest.get('format')!='mathmodel-offline-migration' or manifest.get('version')!=1:raise CommandError('迁移包格式无效。')
        if digest(root/'database.json')!=manifest['databaseSha256']:raise CommandError('数据库清单校验失败。')
        file_map={item['path']:item for item in manifest['files']}
        if len(file_map)!=len(manifest['files']):raise CommandError('迁移包包含重复文件路径。')
        for item in json.loads((root/'database.json').read_text('utf-8')):
            if item['model'] in ['platform_app.asset','platform_app.executionartifact']:
                fields=item['fields'];entry=file_map.get(fields['file'])
                if not entry or entry['size']!=fields['size'] or entry['sha256']!=fields['sha256']:raise CommandError('迁移清单未完整覆盖数据库原件引用。')
        if media.exists() and any(media.iterdir()):raise CommandError('目标原件目录必须为空。')
        validated=[]
        for item in manifest['files']:
            relative=PurePosixPath(item['path']);source=(root/'files'/relative).resolve();dest=(media/relative).resolve()
            if relative.is_absolute() or '..' in relative.parts or '\\' in item['path'] or not source.is_relative_to(root/'files') or not dest.is_relative_to(media):raise CommandError('原件路径无效。')
            if not source.is_file() or source.stat().st_size!=item['size'] or digest(source)!=item['sha256']:raise CommandError('原件SHA或大小不匹配，未恢复数据库。')
            validated.append((source,dest))
        from platform_app.private_storage import protect_private_directory
        protect_private_directory(settings.DATA_DIR)
        # Staging is on the destination filesystem. Failed restores leave an empty DB/media target.
        with tempfile.TemporaryDirectory(prefix='restore-',dir=settings.DATA_DIR) as stage_name:
            stage=Path(stage_name)/'files';stage.mkdir();published=False
            try:
                for source,dest in validated:
                    relative=dest.relative_to(media);staged=stage/relative;staged.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,staged)
                    expected=file_map[relative.as_posix()]
                    if staged.stat().st_size!=expected['size'] or digest(staged)!=expected['sha256']:raise CommandError('原件复制期间变化，恢复已撤销。')
                with transaction.atomic():
                    call_command('loaddata',str(root/'database.json'),verbosity=0)
                    from django.apps import apps
                    for label,count in manifest['counts'].items():
                        model=apps.get_model(label)
                        if model.objects.count()!=count:raise CommandError('恢复后数量不匹配：'+label)
                        identity=hashlib.sha256(json.dumps(sorted(str(pk) for pk in model.objects.values_list('pk',flat=True))).encode()).hexdigest()
                        if identity!=manifest.get('identities',{}).get(label):raise CommandError('恢复后身份主键不匹配：'+label)
                    if media.exists():media.rmdir()  # Empty directory only; never recursively replace existing data.
                    stage.replace(media);published=True
            except Exception:
                if published:
                    # Move back only this run's new directory; TemporaryDirectory cleans the verified stage.
                    media.replace(stage)
                raise
        self.stdout.write('恢复完成；账号、权限、聊天及原件数量和SHA已核对。SECRET_KEY、私有凭据和许可证请从独立秘密备份恢复。')
