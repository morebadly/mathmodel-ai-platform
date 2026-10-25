"""Replaceable retrieval boundary. Keyword chunks are not vector search."""
import hashlib,re
from typing import Protocol
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from .models import Record,SearchChunk,IndexTask,Audit
from .domain import require_verified,can_read,editable,get_record,verified

class RetrievalBackend(Protocol):
    def search(self,user,query,limit):...

class KeywordBackend:
    name='keyword'
    def search(self,user,query,limit=8):
        terms=[t for t in re.split(r'\s+',query.lower()) if t][:12];hits=[]
        if not terms:return []
        for row in Record.objects.filter(collection='resources',payload__kind='knowledge').select_related('team'):
            if not can_read(user,row):continue
            text=row.payload.get('text','');title=row.payload.get('title') or row.payload.get('name','')
            searchable=(title+' '+row.payload.get('tags','')+' '+text).lower()
            score=sum(searchable.count(term) for term in terms)
            if not score:continue
            positions=[text.lower().find(t) for t in terms if text.lower().find(t)>=0];start=max(0,min(positions)-120) if positions else 0;end=min(len(text),start+900)
            hits.append({'resourceId':row.id,'title':title,'quote':text[start:end],'start':start,'end':end,'revision':row.revision,'sourceLabel':row.payload.get('sourceLabel','用户上传'),'location':f'正文字符{start+1}–{end}','downloadUrl':'/api/files/'+row.id,'score':score})
        return sorted(hits,key=lambda h:(-h['score'],h['resourceId']))[:limit]

def backend(name='keyword'):
    if name!='keyword':raise ValidationError('向量检索待服务器部署及真实验收，当前仅提供关键词检索。')
    return KeywordBackend()

@api_view(['GET'])
def search(request):
    require_verified(request.user);q=request.query_params.get('q','').strip()
    if not q or len(q)>500:raise ValidationError('请输入1–500字符的查询。')
    return Response({'backend':'keyword','vectorReady':False,'hits':backend(request.query_params.get('backend','keyword')).search(request.user,q),'note':'这是权限过滤后的关键词检索，引用位置对应指定revision；不是向量或语义检索。'})

@api_view(['GET','POST'])
def index_tasks(request):
    require_verified(request.user)
    if request.method=='GET':
        rows=IndexTask.objects.filter(owner=request.user).order_by('-created_at')[:100]
        return Response({'tasks':[{'id':str(r.id),'provider':r.provider,'action':r.action,'status':r.status,'processed':r.processed,'error':r.error} for r in rows]})
    provider=request.data.get('provider','keyword');action=request.data.get('action','upsert');ids=request.data.get('resourceIds',[])
    if provider not in ['keyword','vector'] or action not in ['upsert','delete'] or not isinstance(ids,list) or not 1<=len(ids)<=200 or any(not isinstance(x,str) for x in ids):raise ValidationError('索引请求无效。')
    for rid in ids:
        row=get_record(request.user,rid,'resources')
        if row.payload.get('kind')!='knowledge' or not editable(request.user,row):raise PermissionDenied('只能维护本人或管理员授权的知识索引。')
    task=IndexTask.objects.create(owner=request.user,provider=provider,action=action,resource_ids=list(dict.fromkeys(ids)),status='awaiting_server' if provider=='vector' else 'queued')
    return Response({'id':str(task.id),'status':task.status,'vectorReady':False},status=202)

@api_view(['POST'])
def cancel_index(request,key):
    require_verified(request.user);task=IndexTask.objects.filter(pk=key,owner=request.user).first()
    if not task:raise NotFound()
    if task.status in ['queued','running','awaiting_server']:task.status='cancelled';task.save()
    return Response({'status':task.status})

def process_indexes(limit=2):
    for key in list(IndexTask.objects.filter(status='queued').order_by('created_at').values_list('id',flat=True)[:limit]):
        with transaction.atomic():
            task=IndexTask.objects.select_for_update().select_related('owner').get(pk=key)
            if task.status!='queued':continue
            task.status='running';task.save()
        try:
            for rid in task.resource_ids:
                with transaction.atomic():
                    current=IndexTask.objects.select_for_update().get(pk=key)
                    if current.status!='running':break
                    row=Record.objects.select_for_update(of=('self',)).select_related('team').filter(pk=rid,collection='resources').first()
                    task.owner.refresh_from_db()
                    if not row or not verified(task.owner) or not can_read(task.owner,row) or not editable(task.owner,row):raise PermissionDenied('索引权限已撤销。')
                    SearchChunk.objects.filter(resource=row).delete()
                    if task.action=='upsert':
                        text=row.payload.get('text','')
                        for start in range(0,len(text),700):
                            chunk=text[start:start+900];SearchChunk.objects.create(resource=row,revision=row.revision,start=start,end=start+len(chunk),text=chunk,sha256=hashlib.sha256(chunk.encode()).hexdigest())
                    current.processed+=1;current.save()
            IndexTask.objects.filter(pk=key,status='running').update(status='completed',updated_at=timezone.now())
        except Exception:IndexTask.objects.filter(pk=key,status='running').update(status='failed',error='索引处理未完成，请核对资料及权限后重试。',updated_at=timezone.now())

def invalidate_resource(resource):
    # Prevent stale chunks from surviving edits, regardless of which UI performs the edit.
    SearchChunk.objects.filter(resource=resource).delete()
