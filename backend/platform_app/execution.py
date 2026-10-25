"""Only remote sandboxes execute user programs. No exec/eval/subprocess user-code fallback."""
import hashlib,json,mimetypes,threading,time,uuid
from pathlib import Path,PurePosixPath
from typing import Protocol
from django.conf import settings
from django.db import transaction,close_old_connections
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound,Throttled
from .domain import require_verified,get_record,can_read,verified
from .models import User,Record,Asset,ExecutionJob,ExecutionArtifact,RuntimeStatus,Audit

ACTIVE=['starting','running','cancel_requested']
TERMINAL=['completed','failed','cancelled','timed_out','access_revoked','uncertain']

def profiles():
    remote=bool(settings.E2B_API_KEY) if settings.SANDBOX_PROVIDER=='e2b' else bool(settings.RUNNER_URL and settings.RUNNER_API_KEY)
    result=[]
    for runtime in ['python','r','matlab','gurobi','cplex']:
        commercial=runtime in ['matlab','gurobi','cplex'];authorized=settings.RUNTIME_AUTHORIZATION.get(runtime,False)
        configured=bool(settings.RUNNER_URL and settings.RUNNER_API_KEY) if commercial else remote
        status='awaiting_authorization' if commercial and not authorized else 'ready_for_remote_test' if configured else 'awaiting_credentials'
        provider_name='gateway' if commercial else settings.SANDBOX_PROVIDER
        accepted=configured and status=='ready_for_remote_test' and ExecutionJob.objects.filter(runtime=runtime,provider=provider_name,status='completed',cleanup_pending=False).exclude(remote_id='').exists()
        note='MATLAB或商业求解器必须获得适用的服务端/云/并发授权。' if commercial else '已有成功的远端任务记录；仅代表已运行的样例，不保证所有依赖包均可用。' if accepted else '代码仅在远程隔离环境执行；凭证配置后仍需真实验收。'
        result.append({'id':runtime,'status':status,'provider':provider_name,'executionVerified':bool(accepted),'maxSeconds':settings.SANDBOX_MAX_SECONDS,'maxInputBytes':settings.SANDBOX_INPUT_BYTES,'maxOutputBytes':settings.SANDBOX_OUTPUT_BYTES,'cpus':settings.SANDBOX_CPUS,'memoryMb':settings.SANDBOX_MEMORY_MB,'note':note})
    return result

def inputs_allowed(job):
    user=User.objects.filter(pk=job.owner_id).first()
    if not user or not verified(user):return False
    for rid in job.input_ids:
        row=Record.objects.select_related('team').filter(pk=rid,collection='resources').first()
        if not row or not can_read(user,row):return False
    return True

def job_json(job,detail=False):
    if not inputs_allowed(job):return {'id':str(job.id),'status':'access_revoked','runtime':job.runtime,'error':'账号或输入文件权限已撤销。','artifacts':[]}
    result={'id':str(job.id),'runtime':job.runtime,'provider':job.provider,'status':job.status,'error':job.error,'cleanupPending':job.cleanup_pending,'limits':job.limits,'attempts':job.attempts,'createdAt':job.created_at.isoformat(),'artifacts':[{'id':str(a.id),'name':a.name,'size':a.size,'mime':a.mime,'url':'/api/execution/artifacts/'+str(a.id)} for a in job.artifacts.all()]}
    if detail:result.update(code=job.code,logs=job.logs,inputIds=job.input_ids)
    return result

@api_view(['GET'])
def runtimes(request):
    require_verified(request.user);rows=profiles();return Response({'runtimes':rows,'hostExecution':False,'realRemoteExecutionAccepted':any(r['executionVerified'] for r in rows)})

@api_view(['GET','POST'])
def jobs(request):
    require_verified(request.user)
    if request.method=='GET':return Response({'jobs':[job_json(j) for j in ExecutionJob.objects.filter(owner=request.user).order_by('-created_at')[:100]]})
    runtime=request.data.get('runtime');code=request.data.get('code','');ids=request.data.get('inputIds',[]);seconds=request.data.get('seconds',60)
    profile=next((p for p in profiles() if p['id']==runtime),None)
    if not profile or not isinstance(code,str) or not code.strip() or len(code)>100000:raise ValidationError('请选择运行环境并提供不超过10万字符的代码。')
    if not isinstance(ids,list) or len(ids)>5 or any(not isinstance(r,str) for r in ids) or len(set(ids))!=len(ids):raise ValidationError('最多选择5个不同的输入文件。')
    if not isinstance(seconds,int) or isinstance(seconds,bool) or not 1<=seconds<=settings.SANDBOX_MAX_SECONDS:raise ValidationError('运行时限超出平台配置。')
    try:client_id=uuid.UUID(str(request.data.get('clientId')))
    except ValueError:raise ValidationError('请提供任务去重标识。')
    total=0
    for rid in ids:
        row=get_record(request.user,rid,'resources');asset=Asset.objects.filter(record=row).first()
        if not asset:raise ValidationError('输入原件不存在。')
        total+=asset.size
    if total>settings.SANDBOX_INPUT_BYTES:raise ValidationError('输入文件总量超过限制。')
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        # Serialize a new file reference with trashing that file. Validation
        # above provides early feedback; this check closes the concurrent gap.
        for rid in sorted(ids):get_record(request.user,rid,'resources',lock=True)
        old=ExecutionJob.objects.filter(owner=request.user,client_id=client_id).first()
        if old:
            if old.runtime!=runtime or old.code!=code or old.input_ids!=ids or old.limits.get('seconds')!=seconds:raise ValidationError('同一去重标识不能对应不同任务。')
            return Response({'job':job_json(old,True),'duplicate':True})
        if ExecutionJob.objects.filter(owner=request.user,created_at__gte=timezone.now()-__import__('datetime').timedelta(days=1)).count()>=settings.SANDBOX_DAILY_JOBS:raise Throttled(detail='已达到当前账号的每日任务限额。')
        if ExecutionJob.objects.filter(owner=request.user,status__in=ACTIVE+['queued']).count()>=5:raise Throttled(detail='待处理任务过多，请先完成或取消。')
        state='queued' if profile['status']=='ready_for_remote_test' else profile['status']
        job=ExecutionJob.objects.create(owner=request.user,client_id=client_id,provider=profile['provider'],runtime=runtime,code=code,input_ids=ids,status=state,limits={'seconds':seconds,'cpus':settings.SANDBOX_CPUS,'memoryMb':settings.SANDBOX_MEMORY_MB,'inputBytes':settings.SANDBOX_INPUT_BYTES,'outputBytes':settings.SANDBOX_OUTPUT_BYTES})
        Audit.objects.create(actor=request.user,action='execution-create',target=str(job.id))
    return Response({'job':job_json(job,True),'duplicate':False},status=202)

@api_view(['GET','POST'])
def job_detail(request,key):
    require_verified(request.user);job=ExecutionJob.objects.filter(pk=key,owner=request.user).first()
    if not job:raise NotFound('任务不存在。')
    if request.method=='GET':
        if not inputs_allowed(job):raise PermissionDenied('输入文件权限已撤销，任务内容不可访问。')
        return Response({'job':job_json(job,True)})
    action=request.data.get('action')
    if action=='cancel':
        with transaction.atomic():
            job=ExecutionJob.objects.select_for_update().get(pk=key)
            if job.status not in TERMINAL:job.status='cancel_requested' if job.remote_id or job.status in ACTIVE else 'cancelled';job.save()
        if job.remote_id and job.status=='cancel_requested':
            guard=ExecutionJob.objects.filter(pk=key,remote_id=job.remote_id,claimed_at=job.claimed_at,status='cancel_requested')
            try:provider(job).cancel(job.remote_id);guard.update(status='cancelled',cleanup_pending=False)
            except Exception:guard.update(cleanup_pending=True,error='取消请求已记录，远端释放尚待确认。')
    elif action=='retry':
        with transaction.atomic():
            job=ExecutionJob.objects.select_for_update().get(pk=key,owner=request.user)
            if job.attempts>=3:raise ValidationError('已达到单个任务的3次尝试上限，请先核对配置。')
            if job.status not in ['awaiting_credentials','awaiting_authorization','failed','timed_out','access_revoked']:raise ValidationError('此状态不能重试；不确定任务须先人工核对远端。')
            if job.cleanup_pending:raise ValidationError('请先核对并释放远端资源。')
            if not inputs_allowed(job):raise PermissionDenied('输入文件已失去权限。')
            profile=next(p for p in profiles() if p['id']==job.runtime)
            job.status='queued' if profile['status']=='ready_for_remote_test' else profile['status'];job.provider=profile['provider'];job.error='';job.remote_id='';job.save(update_fields=['status','provider','error','remote_id','updated_at'])
    else:raise ValidationError('任务操作无效。')
    job.refresh_from_db();return Response({'job':job_json(job,True)})

@api_view(['GET'])
def artifact(request,key):
    require_verified(request.user);item=ExecutionArtifact.objects.select_related('job').filter(pk=key,job__owner=request.user).first()
    if not item:raise NotFound()
    if not inputs_allowed(item.job):raise PermissionDenied('输入权限已撤销，结果不可访问。')
    from .files import protected_file
    response=protected_file(request,item.file,as_attachment=True,filename=item.name,content_type=item.mime);response['Content-Security-Policy']="sandbox; default-src 'none'";response['Cache-Control']='private, no-store';return response

class ExecutionProvider(Protocol):
    def create(self,job):...
    def run(self,job,remote_id,inputs,on_log):...
    def cancel(self,remote_id):...

class OutputLimit(Exception):pass

class E2BProvider:
    def create(self,job):
        from e2b_code_interpreter import Sandbox
        sandbox=Sandbox.create(api_key=settings.E2B_API_KEY,template=settings.E2B_TEMPLATE or None,timeout=job.limits['seconds']+60,allow_internet_access=False,metadata={'mathmodel_job':str(job.id)},request_timeout=20)
        return sandbox.sandbox_id
    def connect(self,remote_id):
        from e2b_code_interpreter import Sandbox
        return Sandbox.connect(sandbox_id=remote_id,api_key=settings.E2B_API_KEY,request_timeout=20)
    def cancel(self,remote_id):
        from e2b_code_interpreter import Sandbox
        Sandbox.kill(sandbox_id=remote_id,api_key=settings.E2B_API_KEY,request_timeout=15)
    def run(self,job,remote_id,inputs,on_log):
        sandbox=self.connect(remote_id);info=sandbox.get_info()
        if info.cpu_count>job.limits['cpus'] or info.memory_mb>job.limits['memoryMb']:raise ValueError('Remote resources exceed approved limits')
        root='/home/user/mathmodel-'+str(job.id);sandbox.files.make_dir(root+'/input');sandbox.files.make_dir(root+'/output')
        for name,data in inputs:sandbox.files.write(root+'/input/'+name,data,request_timeout=20)
        extension='py' if job.runtime=='python' else 'r';sandbox.files.write(root+'/main.'+extension,job.code)
        command=('python' if job.runtime=='python' else 'Rscript')+' main.'+extension
        from e2b.exceptions import TimeoutException
        from e2b import CommandExitException
        try:result=sandbox.commands.run(command,cwd=root,timeout=job.limits['seconds'],request_timeout=job.limits['seconds']+10,on_stdout=on_log,on_stderr=on_log,envs={'MPLBACKEND':'Agg'})
        except TimeoutException:return {'status':'timed_out','error':'远端代码达到执行时限，已安排释放环境。','artifacts':[]}
        except CommandExitException as exc:return {'status':'failed','error':'远端程序执行失败（退出码'+str(exc.exit_code)+'），请查看运行日志检查代码或依赖包。','artifacts':[]}
        artifacts=[];total=0
        if result.exit_code!=0:return {'status':'failed','error':'远端程序返回非零退出码。','artifacts':[]}
        for entry in sandbox.files.list(root+'/output',depth=1,request_timeout=10):
            file_path=PurePosixPath(entry.path)
            if str(getattr(entry,'type','')).lower() not in ['file','filetype.file'] or file_path.parent!=PurePosixPath(root+'/output'):continue
            if entry.size>settings.SANDBOX_OUTPUT_BYTES or len(artifacts)>=20:raise OutputLimit()
            chunks=[];size=0
            with sandbox.files.read(str(file_path),format='stream',request_timeout=20) as stream:
                for chunk in stream:
                    size+=len(chunk);total+=len(chunk)
                    if total>settings.SANDBOX_OUTPUT_BYTES:raise OutputLimit()
                    chunks.append(chunk)
            artifacts.append((file_path.name,b''.join(chunks)))
        return {'status':'completed','error':'','artifacts':artifacts}

class GatewayProvider:
    """Versioned remote-runner contract; server deployment never runs code in this process."""
    def request(self,method,path,**kwargs):
        import httpx
        if not settings.RUNNER_URL.startswith('https://') and not (settings.DEBUG and settings.RUNNER_URL.startswith('http://127.0.0.1:')):raise ValueError('Runner must use HTTPS')
        with httpx.Client(base_url=settings.RUNNER_URL,headers={'Authorization':'Bearer '+settings.RUNNER_API_KEY},timeout=20,follow_redirects=False,trust_env=False) as client:
            with client.stream(method,path,**kwargs) as response:
                if response.status_code==404 and method=='DELETE':return {}
                response.raise_for_status();body=bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body)>settings.SANDBOX_OUTPUT_BYTES*4//3+200000:raise OutputLimit()
                return json.loads(body) if body else {}
    def create(self,job):
        # This reserves an isolated session. Code/files are sent only after the ID is durable.
        result=self.request('POST','/v1/sessions',json={'requestId':str(job.id),'runtime':job.runtime,'limits':job.limits});identifier=result.get('id')
        if not isinstance(identifier,str) or not __import__('re').fullmatch(r'[A-Za-z0-9_-]{1,120}',identifier):raise ValueError('Invalid remote ID')
        return identifier
    def cancel(self,remote_id):self.request('DELETE','/v1/sessions/'+remote_id)
    def run(self,job,remote_id,inputs,on_log):
        import base64
        self.request('POST','/v1/sessions/'+remote_id+'/execute',json={'code':job.code,'inputs':[{'name':name,'base64':base64.b64encode(data).decode()} for name,data in inputs]})
        deadline=time.monotonic()+job.limits['seconds'];offset=0
        while time.monotonic()<deadline:
            payload=self.request('GET','/v1/sessions/'+remote_id+'/status',params={'logOffset':offset});on_log(str(payload.get('logs','')));offset=int(payload.get('logOffset',offset))
            state=payload.get('status')
            if state in TERMINAL:
                files=[];total=0
                for item in payload.get('artifacts',[]):
                    name=item.get('name','');encoded=item.get('base64','')
                    if not isinstance(encoded,str) or len(encoded)>settings.SANDBOX_OUTPUT_BYTES*4//3+16:raise OutputLimit()
                    raw=base64.b64decode(encoded,validate=True);total+=len(raw)
                    if total>settings.SANDBOX_OUTPUT_BYTES or len(files)>=20:raise OutputLimit()
                    files.append((name,raw))
                return {'status':state,'error':'远端执行失败。' if state!='completed' else '','artifacts':files}
            if state not in ['queued','running']:raise ValueError('Invalid remote state')
            time.sleep(.5)
        return {'status':'timed_out','error':'远程执行超时。','artifacts':[]}

def provider(job):
    return E2BProvider() if job.provider=='e2b' else GatewayProvider()

def store_artifacts(job,items):
    total=0;validated=[];names=set();saved=[]
    for name,raw in items:
        if not isinstance(name,str) or PurePosixPath(name).name!=name or '\\' in name or name in ['','.','..'] or len(name)>180:raise ValidationError('结果文件名无效。')
        if not isinstance(raw,bytes) or name in names:raise ValidationError('结果文件格式或重名无效。')
        names.add(name)
        total+=len(raw)
        if total>settings.SANDBOX_OUTPUT_BYTES or len(items)>20:raise OutputLimit()
        mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
        if mime in ['image/png','image/jpeg']:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(raw)) as image:
                if image.width*image.height>16000000:raise OutputLimit()
                image.verify()
        validated.append((name,raw,mime))
    try:
        for name,raw,mime in validated:
            result=ExecutionArtifact(job=job,name=name,size=len(raw),mime=mime,sha256=hashlib.sha256(raw).hexdigest())
            result.file.save(name,ContentFile(raw),save=False);saved.append(result);result.save()
    except Exception:
        for result in saved:result.file.delete(save=False)
        raise

def process_job(key):
    close_old_connections();job=ExecutionJob.objects.get(pk=key);remote=None;stop=threading.Event();watcher=None;attempt_claim=job.claimed_at;identifier=None
    def append_log(text):
        text=str(text)
        with transaction.atomic():
            current=ExecutionJob.objects.select_for_update().get(pk=key)
            if current.claimed_at!=attempt_claim or current.remote_id!=identifier:raise RuntimeError('Stale execution generation')
            if len(current.logs)+len(text)>64000:raise OutputLimit()
            current.logs+=text;current.save(update_fields=['logs','updated_at'])
    def monitor():
        close_old_connections()
        try:
            deadline=time.monotonic()+job.limits['seconds']+30
            while not stop.wait(.5):
                current=ExecutionJob.objects.get(pk=key)
                if current.remote_id!=identifier or current.claimed_at!=attempt_claim:return
                expired=time.monotonic()>deadline
                if current.status=='cancel_requested' or expired or not inputs_allowed(current):
                    state='cancelled' if current.status=='cancel_requested' else 'timed_out' if expired else 'access_revoked'
                    try:remote.cancel(identifier);ExecutionJob.objects.filter(pk=key,remote_id=identifier,claimed_at=attempt_claim,status__in=ACTIVE).update(status=state,cleanup_pending=True)
                    except Exception:ExecutionJob.objects.filter(pk=key,remote_id=identifier,claimed_at=attempt_claim,status__in=ACTIVE).update(cleanup_pending=True)
                    return
        finally:close_old_connections()
    try:
        if not inputs_allowed(job):ExecutionJob.objects.filter(pk=key,claimed_at=attempt_claim).update(status='access_revoked');return
        remote=provider(job);identifier=remote.create(job)
        if not ExecutionJob.objects.filter(pk=key,claimed_at=attempt_claim,status__in=['starting','cancel_requested']).update(remote_id=identifier,cleanup_pending=True):return
        job.refresh_from_db()
        if job.status=='cancel_requested' or not inputs_allowed(job):remote.cancel(identifier);ExecutionJob.objects.filter(pk=key,claimed_at=attempt_claim,remote_id=identifier).update(status='cancelled' if job.status=='cancel_requested' else 'access_revoked',cleanup_pending=True);return
        if not ExecutionJob.objects.filter(pk=key,claimed_at=attempt_claim,remote_id=identifier,status='starting').update(status='running'):return
        job.refresh_from_db();watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
        inputs=[]
        for i,rid in enumerate(job.input_ids):
            row=get_record(job.owner,rid,'resources');asset=Asset.objects.get(record=row)
            if not inputs_allowed(job):raise PermissionDenied()
            if asset.size>settings.SANDBOX_INPUT_BYTES:raise ValidationError('Input too large')
            with asset.file.open('rb') as stream:data=stream.read(settings.SANDBOX_INPUT_BYTES+1)
            if len(data)>settings.SANDBOX_INPUT_BYTES:raise OutputLimit()
            inputs.append((str(i)+'-'+Path(asset.original_name.replace('\\','/')).name[:160],data))
        result=remote.run(job,identifier,inputs,append_log)
        with transaction.atomic():
            current=ExecutionJob.objects.select_for_update().get(pk=key)
            if current.claimed_at!=attempt_claim or current.remote_id!=identifier:return
            if current.status in ['cancelled','access_revoked','cancel_requested','timed_out']:return
            if not inputs_allowed(current):current.status='access_revoked'
            else:
                if result['status']=='completed':
                    for artifact in current.artifacts.all():artifact.file.delete(save=False)
                    current.artifacts.all().delete();store_artifacts(current,result['artifacts'])
                current.status=result['status'];current.error=result.get('error','')[:500]
            current.save()
    except PermissionDenied:ExecutionJob.objects.filter(pk=key,claimed_at=attempt_claim,status__in=ACTIVE).update(status='access_revoked',error='输入文件权限已撤销，执行已停止。')
    except OutputLimit:ExecutionJob.objects.filter(pk=key,claimed_at=attempt_claim,status__in=ACTIVE).update(status='failed',error='远端日志或结果超过平台限制，执行已停止。')
    except Exception:
        current=ExecutionJob.objects.get(pk=key)
        if current.status in ACTIVE and current.claimed_at==attempt_claim:
            ExecutionJob.objects.filter(pk=key,claimed_at=attempt_claim,status__in=ACTIVE).update(status='uncertain' if not current.remote_id else 'failed',error='远程请求未完成；未生成模拟结果。创建状态不确定时需先核对远端。')
    finally:
        stop.set()
        if watcher:watcher.join(timeout=25)
        current=ExecutionJob.objects.get(pk=key)
        if remote and identifier:
            guard=ExecutionJob.objects.filter(pk=key,remote_id=identifier,claimed_at=attempt_claim)
            try:remote.cancel(identifier);guard.update(cleanup_pending=False)
            except Exception:guard.update(cleanup_pending=True)
        close_old_connections()

def dispatch(limit=2):
    for _ in range(limit):
        with transaction.atomic():
            RuntimeStatus.objects.get_or_create(name='execution-dispatch',defaults={'last_seen':timezone.now()})
            RuntimeStatus.objects.select_for_update().get(name='execution-dispatch')
            if ExecutionJob.objects.filter(__import__('django.db.models',fromlist=['Q']).Q(status__in=ACTIVE)|__import__('django.db.models',fromlist=['Q']).Q(cleanup_pending=True)).count()>=settings.SANDBOX_CONCURRENCY:return
            active_owners=ExecutionJob.objects.filter(status__in=ACTIVE).values('owner_id')
            job=ExecutionJob.objects.select_for_update().filter(status='queued').exclude(owner_id__in=active_owners).order_by('created_at').first()
            if not job:return
            if ExecutionJob.objects.filter(owner=job.owner,status__in=ACTIVE).exists():return
            profile=next(p for p in profiles() if p['id']==job.runtime)
            if profile['status']!='ready_for_remote_test':job.status=profile['status'];job.save();continue
            job.status='starting';job.attempts+=1;job.claimed_at=timezone.now();job.logs='';job.save()
        process_job(job.pk)

def reap():
    # Never re-execute a lost job: its upstream side effects could already have happened.
    for job in ExecutionJob.objects.filter(status__in=ACTIVE,claimed_at__lt=timezone.now()-__import__('datetime').timedelta(seconds=settings.SANDBOX_MAX_SECONDS+120)):
        cleanup=job.cleanup_pending
        if job.remote_id:
            try:provider(job).cancel(job.remote_id);cleanup=False
            except Exception:cleanup=True
        ExecutionJob.objects.filter(pk=job.pk,remote_id=job.remote_id,claimed_at=job.claimed_at,status=job.status).update(status='uncertain',cleanup_pending=cleanup,error='执行进程中断，已停止自动重试，请核对远端会话。')
    for job in ExecutionJob.objects.filter(cleanup_pending=True).exclude(status__in=ACTIVE)[:10]:
        if job.remote_id:
            try:provider(job).cancel(job.remote_id);ExecutionJob.objects.filter(pk=job.pk,remote_id=job.remote_id,claimed_at=job.claimed_at,status=job.status).update(cleanup_pending=False,updated_at=timezone.now())
            except Exception:pass
