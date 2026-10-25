"""Copy the approved legacy library into the central account database, read-only at source."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from platform_app.access import fixed_admin
from platform_app.domain import SHARED_SCOPE,valid_id
from platform_app.models import User,Record,Asset,Audit

MARKER='shared-library-v1'

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def safe_name(value):
    return Path(str(value).replace('\\','/')).name[:240] or '原始附件'

def write_snapshot(destination,raw):
    with tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.entry-',delete=False) as stream:
        temporary=Path(stream.name)
        try:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        except BaseException:
            stream.close();temporary.unlink(missing_ok=True);raise
    try:
        if os.name=='nt':os.rename(temporary,destination)
        else:os.link(temporary,destination)
    finally:temporary.unlink(missing_ok=True)

def is_imported(row,owner,source_id,kind,relative,sha):
    if row.collection!='resources' or row.owner_id!=owner.id or row.scope!='public':return False
    if any(row.payload.get(key)!=value for key,value in {'libraryImport':MARKER,'librarySourceId':source_id,'kind':kind,'scope':SHARED_SCOPE}.items()):return False
    asset=Asset.objects.filter(record=row).first()
    return bool(asset and asset.file.name==relative.as_posix() and asset.sha256==sha)

class Command(BaseCommand):
    help='只读导入旧版 library.sqlite；正文和去重原件复制到当前公共知识库，重复执行保留管理员修改。'
    def add_arguments(self,parser):
        parser.add_argument('--source',required=True)
        parser.add_argument('--owner',default='admin01')
        parser.add_argument('--dry-run',action='store_true')
    def handle(self,*args,**options):
        owner=User.objects.filter(admin_login=options['owner']).first()
        if not owner or not fixed_admin(owner):raise CommandError('请选择有效的固定管理员作为公共知识维护者。')
        source=Path(options['source']).resolve()
        if not source.is_file():raise CommandError('未找到来源知识库数据库。')
        database=sqlite3.connect(':memory:');database.row_factory=sqlite3.Row
        try:
            # A consistent read-only snapshot also includes committed WAL contents.
            with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as origin:origin.backup(database)
            resources=[dict(row) for row in database.execute('SELECT * FROM library_resources ORDER BY id')]
            assets=[dict(row) for row in database.execute('SELECT * FROM library_assets ORDER BY id')]
            links={}
            for row in database.execute('SELECT * FROM library_resource_assets ORDER BY resource_id,asset_id'):
                links.setdefault(row['resource_id'],[]).append(dict(row))
        except sqlite3.Error:raise CommandError('来源知识库结构无效，未导入。')
        finally:database.close()
        source_root=source.parent;media=Path(settings.MEDIA_ROOT).resolve();prepared={}
        for item in assets:
            original=(source_root/item['path']).resolve()
            sha=item['sha256']
            if not re.fullmatch(r'[a-f0-9]{64}',sha) or not original.is_relative_to(source_root) or not original.is_file():raise CommandError('附件路径或标识无效：'+item['id'])
            if original.stat().st_size!=item['size'] or digest(original)!=sha:raise CommandError('附件完整性检查失败：'+item['id'])
            extension='.pdf' if item['mime']=='application/pdf' else Path(safe_name(item['original_name'])).suffix.lower()
            if not re.fullmatch(r'\.[a-z0-9]{1,10}',extension):extension='.bin'
            relative=Path('shared-library/assets')/(sha+extension)
            prepared[item['id']]={**item,'source':original,'relative':relative,'id':'sharedasset_'+sha}
        for row in resources:
            if not valid_id(row['id']):raise CommandError('资料标识无效，未导入。')
            if any(link['asset_id'] not in prepared for link in links.get(row['id'],[])):raise CommandError('资料缺少关联附件，未导入。')
        self.stdout.write(f"来源完整性通过：{len(resources)} 条资料，{len(assets)} 个去重附件。")
        if options['dry_run']:return
        # Copy by digest, never move or modify the original database/attachments.
        for number,item in enumerate(prepared.values(),1):
            destination=media/item['relative'];destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists():
                if digest(destination)!=item['sha256']:raise CommandError('目标附件与校验值不一致，未覆盖。')
            else:
                with tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.copy-',delete=False) as stream:temporary=Path(stream.name)
                try:
                    shutil.copyfile(item['source'],temporary)
                    if digest(temporary)!=item['sha256']:raise CommandError('复制后附件校验失败，未发布文件。')
                    temporary.replace(destination)
                finally:temporary.unlink(missing_ok=True)
            if number%50==0:self.stdout.write(f'已核对并复制附件 {number}/{len(assets)}')
        created=0;skipped=0
        with transaction.atomic():
            for item in prepared.values():
                existing=Record.objects.filter(pk=item['id']).first()
                if existing:
                    if not is_imported(existing,owner,item['id'],'attachment',item['relative'],item['sha256']):raise CommandError('原件标识已被其他记录使用，未覆盖。')
                    continue
                payload={'id':item['id'],'name':safe_name(item['original_name']),'kind':'attachment','category':'','scope':SHARED_SCOPE,'tags':'','description':'公共知识库来源原件','text':'','size':item['size'],'type':item['mime'],'createdAt':timezone.now().isoformat(),'parseStatus':'saved_only','libraryImport':MARKER,'librarySourceId':item['id']}
                record=Record.objects.create(id=item['id'],collection='resources',owner=owner,scope='public',payload=payload)
                Asset.objects.create(record=record,file=item['relative'].as_posix(),original_name=payload['name'],size=item['size'],sha256=item['sha256'],content_type=item['mime'],parse_status='saved_only')
            for row in resources:
                try:tags=json.loads(row['tags_json'])
                except (ValueError,TypeError):tags=[]
                attachments=[{'id':prepared[link['asset_id']]['id'],'label':link['label'],'role':link['role']} for link in links.get(row['id'],[])]
                title=str(row['title'])[:235];name=title+'.md';full_text=str(row['body_text']);text=full_text[:1000000]
                status='partial' if len(full_text)>len(text) else 'ready';warning='检索正文限100万字符，下载快照保留完整正文。' if status=='partial' else ''
                markdown='# '+title+'\n\n'+full_text+'\n\n来源：'+str(row['source_label'])+'\n'+str(row['source_url'])
                raw=markdown.encode('utf-8');relative=Path('shared-library/entries')/(row['id']+'.md');destination=media/relative
                snapshot_sha=hashlib.sha256(raw).hexdigest()
                existing=Record.objects.filter(pk=row['id']).first()
                if existing:
                    if not is_imported(existing,owner,row['id'],'knowledge',relative,snapshot_sha) or existing.payload.get('libraryAssetIds')!=attachments:raise CommandError('资料标识或原件映射不一致，未覆盖。')
                    if destination.exists():
                        if destination.stat().st_size!=len(raw) or digest(destination)!=snapshot_sha:raise CommandError('已有正文文件校验失败，未覆盖损坏文件。')
                    else:
                        destination.parent.mkdir(parents=True,exist_ok=True);write_snapshot(destination,raw)
                    skipped+=1;continue
                destination.parent.mkdir(parents=True,exist_ok=True)
                if destination.exists() and destination.read_bytes()!=raw:raise CommandError('目标正文文件已存在不同内容，未覆盖。')
                if not destination.exists():write_snapshot(destination,raw)
                payload={'id':row['id'],'title':title,'name':name,'kind':'knowledge','category':row['category'],'scope':SHARED_SCOPE,'tags':' '.join(str(t) for t in tags) if isinstance(tags,list) else '',
                         'description':str(row['summary'])+'\n'+str(row['note']),'text':text,'size':len(raw),'type':'text/markdown','createdAt':row['created_at'],'parseStatus':status,'parseWarning':warning,
                         'libraryImport':MARKER,'librarySourceId':row['id'],'libraryAssetIds':attachments,'sourceLabel':row['source_label'],'sourceUrl':row['source_url'],'availability':row['availability'],'sourceKind':row['kind']}
                record=Record.objects.create(id=row['id'],collection='resources',owner=owner,scope='public',payload=payload)
                Asset.objects.create(record=record,file=relative.as_posix(),original_name=name,size=len(raw),sha256=snapshot_sha,content_type='text/markdown',parse_status=status,parse_error=warning);created+=1
            Audit.objects.create(actor=owner,action='shared-library-import',target=str(created)+' records; '+str(len(assets))+' assets')
        self.stdout.write(f'公共知识库已就绪：新增 {created}，保留已有 {skipped}；原件 {len(assets)}。')
