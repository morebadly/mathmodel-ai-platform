import importlib.util,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from .models import Asset,Audit,Record
from .domain import require_verified,get_record,editable
from .processes import spawn_helper,terminate_tree,close_job

def capabilities():
    model_dir=Path(settings.MEDIA_MODEL_DIR)
    return {'ocr':bool(importlib.util.find_spec('rapidocr_onnxruntime')),'ffmpeg':bool(shutil.which(settings.FFMPEG_PATH) or Path(settings.FFMPEG_PATH).is_file()),'speechLanguages':[lang for lang,folder in [('en','vosk-model-small-en-us-0.15'),('zh','vosk-model-small-cn-0.22')] if (model_dir/folder).is_dir()],'ocrPageLimit':20,'speechSecondsLimit':600,'vectorReady':False}

def process(asset,mode,language):
    with tempfile.TemporaryDirectory(prefix='media-',dir=settings.DATA_DIR) as folder:
        result_path=Path(folder)/'result.json';env={**os.environ,'TEMP':folder,'TMP':folder}
        command=[sys.executable,str(settings.BASE_DIR/'tools/process_media.py'),'--input',asset.file.path,'--output',str(result_path),'--mode',mode,'--language',language,'--models',str(settings.MEDIA_MODEL_DIR),'--ffmpeg',settings.FFMPEG_PATH]
        with spawn_helper(command,env) as child:
            try:
                deadline=time.monotonic()+settings.MEDIA_TASK_TIMEOUT
                while child.poll() is None:
                    state=Asset.objects.filter(pk=asset.pk).values('parse_status','claimed_at').first()
                    if not state or state['parse_status']!='processing' or state['claimed_at']!=asset.claimed_at or time.monotonic()>deadline:
                        terminate_tree(child)
                        try:child.wait(timeout=5)
                        except subprocess.TimeoutExpired:child.kill();child.wait()
                        return '', 'cancelled' if state and state['parse_status']=='cancelled' else 'failed','处理取消或超时，原件保留。',{}
                    time.sleep(.25)
            finally:
                try:
                    if child.poll() is None:
                        terminate_tree(child)
                        try:child.wait(timeout=5)
                        except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
                finally:close_job(child)
        if not result_path.is_file() or result_path.stat().st_size>8*1024*1024:return '', 'failed','媒体处理结果缺失或超过限制，原件保留。',{}
        result=json.loads(result_path.read_text('utf-8'));text=result.get('text','')
        if len(text)>1000000:text=text[:1000000];result.update(status='partial',warning='检索文本截断到100万字符，原件保留。')
        return text,result['status'],result.get('warning',''),{'parseEngine':result.get('engine',''),'parseSegments':result.get('segments',[])[:10000],'durationSeconds':result.get('durationSeconds')}

@api_view(['GET','POST'])
def status(request,key):
    require_verified(request.user);row=get_record(request.user,key,'resources');asset=Asset.objects.filter(record=row).first()
    if not asset:raise NotFound('原件不存在。')
    if request.method=='POST':
        if not editable(request.user,row):raise PermissionDenied('只有资料所有者或管理员可以安排解析。')
        action=request.data.get('action','retry');mode=request.data.get('mode','auto');language=request.data.get('language','zh')
        if mode not in ['auto','ocr','transcribe'] or language not in ['zh','en']:raise ValidationError('解析方式或语言无效。')
        with transaction.atomic():
            # Match parser lock order and merge only the control fields into the latest payload.
            asset=Asset.objects.select_for_update().get(pk=asset.pk)
            row=Record.objects.select_for_update().get(pk=key)
            if not editable(request.user,row):raise PermissionDenied('解析权限已变化。')
            if action=='cancel':
                asset.parse_status='cancelled';asset.parse_error='用户取消解析。';row.payload['parseStatus']='cancelled'
            elif action=='retry':
                if asset.parse_status in ['pending','processing']:raise ValidationError('解析正在排队或进行中，请勿重复提交。')
                row.payload.update(parseMode=mode,parseLanguage=language,parseStatus='pending');asset.parse_status='pending';asset.parse_error=''
            else:raise ValidationError('解析操作无效。')
            asset.claimed_at=None;asset.save()
            row.revision+=1;row.save(update_fields=['payload','revision','updated_at']);Audit.objects.create(actor=request.user,action='parse-'+action,target=key)
    return Response({'id':key,'status':asset.parse_status,'warning':asset.parse_error,'mode':row.payload.get('parseMode','auto'),'language':row.payload.get('parseLanguage','zh'),'engine':row.payload.get('parseEngine',''),'textPreview':row.payload.get('text','')[:20000],'capabilities':capabilities()})
