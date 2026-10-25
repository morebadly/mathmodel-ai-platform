import copy
import json
import re
import uuid
import hashlib
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound,APIException
from allauth.account.models import EmailAddress
from .models import User,Record,Membership,Workspace,Usage,Audit,AIRun

COLLECTIONS=['projects','resources','papers','tasks','competitions','conversations','writingDrafts','teams','supervisionPlans','reminderDrafts','scoreRecords','usageRecords','taskSubmissions','notifications']
PRIVILEGED={'teams','supervisionPlans','reminderDrafts','scoreRecords','notifications'}
SHARED_SCOPE='公共知识库'
RESOURCE_SCOPES={'个人资料':'private','公开资料':'public','校内资料':'school','教师私有':'teacher',SHARED_SCOPE:'public'}

def resource_scope(user,data):
    scope=data.get('scope') or '个人资料'
    if scope not in RESOURCE_SCOPES:raise ValidationError('资料分区无效。')
    if scope==SHARED_SCOPE and user.role!='admin':raise PermissionDenied('公共知识库由管理员维护。')
    if scope=='教师私有' and user.role=='student':raise PermissionDenied('教师私有分区仅供导师使用。')
    return RESOURCE_SCOPES[scope]
class Conflict(APIException):
    status_code=409
    default_detail='其他页面已更新此记录，请同步后再保存。'

def valid_id(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{8,100}',value))
def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if not k.startswith('_')}
    if isinstance(value,list):return [clean(x) for x in value]
    return value
def equal(a,b):return json.dumps(clean(a),sort_keys=True,ensure_ascii=False)==json.dumps(clean(b),sort_keys=True,ensure_ascii=False)
def verified(user):
    if user.role=='admin':
        from .access import fixed_admin
        return fixed_admin(user)
    return user.is_active and EmailAddress.objects.filter(user=user,email__iexact=user.email,verified=True).exists()
def require_verified(user):
    if not user.is_authenticated or not verified(user):raise PermissionDenied('请先验证邮箱并登录。')
def managed_users(user):
    if user.role=='admin':return User.objects.all()
    if user.role!='mentor':return User.objects.filter(id=user.id)
    ids=list(Membership.objects.filter(team__owner=user,team__collection='teams').values_list('user_id',flat=True))
    return User.objects.filter(Q(id=user.id)|Q(id__in=ids))
def can_read(user,row):
    if row.scope=='deleted':return False
    if row.collection=='resources' and row.payload.get('chatRoomId'):
        from .chat import allowed_room
        try:allowed_room(user,row.payload['chatRoomId']);return True
        except NotFound:return False
    if user.role=='admin':return True
    # Student analytics need current supervision or this score's task-review permission.
    if row.collection in ['scoreRecords','usageRecords']:
        if row.collection=='scoreRecords' and user.role=='mentor' and row.payload.get('submissionId'):
            submission=Record.objects.filter(id=row.payload['submissionId'],collection='taskSubmissions').first()
            if submission and submission.payload.get('personId')==row.payload.get('personId') and Record.objects.filter(id=submission.payload.get('taskId'),collection='tasks',owner=user).exists():return True
        return str(user.id)==row.payload.get('personId') or (user.role=='mentor' and managed_users(user).filter(id=row.payload.get('personId')).exists())
    if row.owner_id==user.id:return True
    if row.collection in ['supervisionPlans','reminderDrafts']:
        return str(user.id) in row.payload.get('studentIds',row.payload.get('recipientIds',[]))
    if row.collection=='taskSubmissions':
        task=Record.objects.filter(id=row.payload.get('taskId'),collection='tasks').first()
        return bool(user.role=='mentor' and task and task.owner_id==user.id)
    if row.collection=='notifications':return str(user.id)==row.payload.get('personId')
    if row.scope in ['public','school'] and row.collection in ['resources','tasks']:return True
    if row.team_id and (row.collection!='resources' or row.id in row.team.payload.get('fileIds',[])) and (row.team.owner_id==user.id or Membership.objects.filter(team_id=row.team_id,user=user).exists()):return True
    if row.collection=='resources':
        if not hasattr(user,'_task_attachments'):
            user._task_attachments={key for task in Record.objects.filter(collection='tasks').select_related('team') if can_read(user,task) for key in task.payload.get('attachmentIds',[])}
        if row.id in user._task_attachments:return True
    if user.role=='mentor' and row.collection in ['resources','papers']:
        if not hasattr(user,'_submission_refs'):
            tasks=list(Record.objects.filter(collection='tasks',owner=user).values_list('id',flat=True))
            submissions=Record.objects.filter(collection='taskSubmissions',payload__taskId__in=tasks)
            refs={'resources':set(),'papers':set()}
            for submission in submissions:
                refs['resources'].update(submission.payload.get('snapshot',{}).get('resourceIds',[]))
                refs['papers'].update(submission.payload.get('paperIds',[]))
            user._submission_refs=refs
        if row.id in user._submission_refs[row.collection]:return True
    if row.scope=='teacher':return False
    if row.collection=='teams':return Membership.objects.filter(team=row,user=user).exists()
    return False
def get_record(user,key,collection=None,lock=False):
    rows=Record.objects.select_related('team')
    if lock:rows=rows.select_for_update(of=('self',))
    row=rows.filter(id=key).first()
    if not row or (collection and row.collection!=collection) or not can_read(user,row):raise NotFound('记录不存在或无权访问。')
    return row
def editable(user,row):
    if row.scope=='deleted':return False
    if row.collection=='resources' and row.payload.get('chatRoomId') and not can_read(user,row):return False
    if row.collection in ['scoreRecords','usageRecords'] and not can_read(user,row):return False
    if user.role=='admin' or row.owner_id==user.id:return True
    if row.collection=='taskSubmissions' and user.role=='mentor':
        return Record.objects.filter(id=row.payload.get('taskId'),owner=user,collection='tasks').exists()
    if row.collection=='papers' and user.role=='mentor':
        task_ids=list(Record.objects.filter(collection='tasks',owner=user).values_list('id',flat=True))
        return any(row.id in s.payload.get('paperIds',[]) for s in Record.objects.filter(collection='taskSubmissions',payload__taskId__in=task_ids))
    return False
def person_json(user):
    # Mailbox proof is independent of account activation; verified() also checks
    # access eligibility and must remain the gate for authentication/permissions.
    email_verified = user.role!='admin' and EmailAddress.objects.filter(user=user,email__iexact=user.email,verified=True).exists()
    return {'id':str(user.id),'role':'mentor' if user.role in ['mentor','admin'] else 'student','accountRole':user.role,'adminLogin':user.admin_login or '', 'requestedRole':user.requested_role,'isActive':user.is_active,'name':user.display_name or user.email.split('@')[0],'email':user.email,'emailVerified':email_verified,'identifier':'','cohort':user.cohort,'contactConsent':'granted' if user.reminder_consent else 'declined','createdAt':user.date_joined.isoformat()}
def record_json(row,user=None):
    data=clean(copy.deepcopy(row.payload))
    if user and row.collection=='teams' and row.owner_id!=user.id and user.role!='admin':
        data.update(messages=[],members=[])
    return {**data,'id':row.id,'_revision':row.revision,'_ownerId':str(row.owner_id)}
def usage_json(row):
    return {'id':str(row.id),'personId':str(row.user_id),'startedAt':row.started_at.isoformat(),'endedAt':row.ended_at.isoformat(),'activity':row.activity,'module':'、'.join(row.modules),'source':'服务端自动记录 · 已验证邮箱账号','createdAt':row.started_at.isoformat(),'capture':'server','_managed':True}
def workspace_json(user):
    workspace,_=Workspace.objects.get_or_create(user=user)
    rows=[r for r in Record.objects.select_related('team').all() if can_read(user,r)]
    state={key:[] for key in COLLECTIONS}
    ownership={}
    for row in rows:
        state[row.collection].append(record_json(row,user));ownership[row.collection+'/'+row.id]=str(row.owner_id)
    users=managed_users(user) if user.role in ['mentor','admin'] else User.objects.filter(id=user.id)
    state['participants']=[person_json(p) for p in users]
    # A school-task reviewer sees the submitter's display name on that submission,
    # without acquiring the student's complete profile or supervision relationship.
    for row in state['taskSubmissions']:
        person=User.objects.filter(id=row.get('personId')).first()
        if person:row['_studentName']=person.display_name or '学生'
    if user.role=='admin':state['usageRecords'] += [usage_json(r) for r in Usage.objects.all()]
    else:state['usageRecords'] += [usage_json(r) for r in Usage.objects.filter(user__in=users)]
    state.update(schemaVersion=1,events=[],teacherProfile={'name':user.display_name,'institution':user.cohort},integritySettings=workspace.preferences.get('integritySettings',{'competitionPeriod':False}),contentOwnership=ownership,spacePreferences={'selectedStudentId':str(user.id) if user.role=='student' else ''},emailPreferences={'captureEnabled':user.track_usage,'journalId':'server'},settings={'role':{'student':'学生视图','mentor':'教师视图','admin':'管理视图'}[user.role],'provider':'openai-compatible','endpoint':settings.SITE_URL+'/api/ai','model':settings.AI_MODEL,'weights':workspace.preferences.get('weights',[15,10,20,15,15,10,15])})
    state['lastConversationId']=workspace.preferences.get('lastConversationId','')
    return state
def require_text(data,key,limit=200000,empty=True):
    value=data.get(key,'')
    if not isinstance(value,str) or len(value)>limit or (not empty and not value.strip()):raise ValidationError('字段无效：'+key)
    return value
def reference(user,key,collection=None,owned=False):
    if not valid_id(key):raise ValidationError('关联标识无效。')
    # Reference creation and deletion must serialize on the referenced row. A
    # lookup outside a transaction remains a read-only permission check.
    row=get_record(user,key,collection,lock=transaction.get_connection().in_atomic_block)
    if owned and row.owner_id!=user.id and user.role!='admin':raise PermissionDenied('不能关联其他用户的私有内容。')
    return row
def target_students(user,ids):
    if not isinstance(ids,list) or not ids:raise ValidationError('请选择学生。')
    allowed={str(p.id) for p in managed_users(user).filter(role='student')}
    if not set(ids)<=allowed:raise PermissionDenied('只能操作自己负责的学生。')

def clear_team_file_access(team,resource_ids):
    """Revoke only this team's obsolete file share; preserve other ACL paths."""
    versions={}
    for resource in Record.objects.select_for_update(of=('self',)).filter(collection='resources',team=team,id__in=resource_ids).order_by('id'):
        resource.team=None;resource.payload=copy.deepcopy(resource.payload)
        if resource.payload.get('teamId')==team.id:resource.payload.pop('teamId')
        resource.revision+=1;resource.save(update_fields=['team','payload','revision','updated_at'])
        versions['resources/'+resource.id]=resource.revision
    return versions

def lock_workspace_resources(changes):
    """Lock resources and parent dependencies in one shared, stable order."""
    ids=set();parent_ids=[];parents={name:set() for name in COLLECTIONS if name!='resources'}
    for collection,items in changes.items():
        if not isinstance(items,list) or len(items)>2000:raise ValidationError('待保存记录列表无效。')
        for item in items:
            if not isinstance(item,dict):raise ValidationError('记录格式无效。')
            if collection=='resources' and valid_id(item.get('id')):ids.add(item['id'])
            elif valid_id(item.get('id')):parents[collection].add(item['id'])
            for field in ['resourceIds','attachmentIds','fileIds']:
                values=item.get(field,[])
                if isinstance(values,list):ids.update(value for value in values if valid_id(value))
            if collection=='papers' and valid_id(item.get('fileId')):ids.add(item['fileId'])
            if collection=='teams' and valid_id(item.get('id')):parent_ids.append(item['id'])
            if collection!='resources' and valid_id(item.get('teamId')):parents['teams'].add(item['teamId'])
            if collection in ['projects','taskSubmissions'] and valid_id(item.get('taskId')):parents['tasks'].add(item['taskId'])
            if collection in ['papers','competitions','taskSubmissions'] and valid_id(item.get('projectId')):parents['projects'].add(item['projectId'])
            if collection=='scoreRecords' and valid_id(item.get('submissionId')):parents['taskSubmissions'].add(item['submissionId'])
    for values in Record.objects.filter(collection='teams',pk__in=parent_ids).values_list('payload__fileIds',flat=True):
        if isinstance(values,list):ids.update(value for value in values if valid_id(value))
    if ids:list(Record.objects.select_for_update(of=('self',)).filter(collection='resources',pk__in=ids).order_by('id').values_list('id',flat=True))
    for collection in ['teams','tasks','projects','papers','competitions','conversations','writingDrafts','supervisionPlans','reminderDrafts','taskSubmissions','scoreRecords','usageRecords','notifications']:
        if parents[collection]:list(Record.objects.select_for_update(of=('self',)).filter(collection=collection,pk__in=parents[collection]).order_by('id').values_list('id',flat=True))

def validate_record(user,collection,data,old=None):
    if not isinstance(data,dict) or not valid_id(data.get('id')):raise ValidationError('记录标识无效。')
    data=clean(data)
    # Resource sharing is maintained by the team file workflow, never by an
    # echoed browser metadata snapshot. In particular, a confirmed new revision
    # must not let a stale teamId resurrect a share just removed from fileIds.
    if collection=='resources':data.pop('teamId',None)
    for field in ['resourceIds','attachmentIds','fileIds','members','messages','annotations','findings','aiReviews']:
        if field=='members' and collection=='competitions':continue
        if field in data and (not isinstance(data[field],list) or len(data[field])>2000):raise ValidationError('列表字段无效：'+field)
    if collection=='competitions':
        require_text(data,'members')
        for key in data.get('attachmentIds',[]):reference(user,key,'resources')
        if data.get('projectId'):
            linked_project=reference(user,data['projectId'],'projects',owned=True)
            if linked_project.payload.get('competitionId') not in [None,'',data['id']]:raise Conflict('配套项目已关联其他比赛，请同步后重试。')
    if collection in PRIVILEGED and user.role not in ['mentor','admin']:raise PermissionDenied('此操作需要导师或管理员权限。')
    if collection=='notifications':raise PermissionDenied('通知由团队发布流程创建。')
    if collection in ['projects','papers','tasks','competitions','conversations','writingDrafts','supervisionPlans','reminderDrafts']:
        require_text(data,'title',240,False)
    team=None
    if data.get('teamId'):
        team=reference(user,data['teamId'],'teams')
        if team.owner_id!=user.id and user.role!='admin':raise PermissionDenied('只能向自己的团队分配内容。')
    if collection=='projects':
        stages=data.get('stages')
        if not isinstance(stages,list) or len(stages)!=8:raise ValidationError('项目需要八个阶段。')
        for stage in stages:
            if not isinstance(stage,dict):raise ValidationError('阶段格式无效。')
            require_text(stage,'title',240,False);require_text(stage,'content')
            if not isinstance(stage.get('done'),bool):raise ValidationError('阶段状态无效。')
        for key in data.get('resourceIds',[]):reference(user,key,'resources')
        if data.get('taskId'):reference(user,data['taskId'],'tasks')
    if collection=='resources':
        require_text(data,'name',240,False);require_text(data,'text',1000000)
        if old is None:raise ValidationError('请通过文件上传接口保存原件。')
        resource_scope(user,data)
        for field in ['libraryImport','librarySourceId','libraryAssetIds','sourceLabel','sourceUrl','availability','sourceKind','chatRoomId']:
            if data.get(field)!=old.payload.get(field):raise ValidationError('资料来源及原件关联由服务端维护，不能新增或改写。')
        if old.payload.get('chatRoomId') and data.get('scope')!='个人资料':raise PermissionDenied('会话附件不能改成公共资料。')
    if collection=='papers':
        reference(user,data.get('fileId'),'resources')
        if old and data.get('fileId')!=old.payload.get('fileId'):raise ValidationError('论文原件不可替换，请上传新版本。')
        if old and old.owner_id!=user.id and user.role!='admin':
            mutable={'annotations','scores','scoredAt','findings','checkedAt','aiReviews','updatedAt'}
            if not equal({k:v for k,v in data.items() if k not in mutable},{k:v for k,v in old.payload.items() if k not in mutable}):raise PermissionDenied('导师只能修改论文反馈，不能改写原文与归属。')
        if data.get('projectId'):
            if old and data['projectId']==old.payload.get('projectId'):
                team=old.team
            else:
                project=reference(user,data['projectId'],'projects',owned=True)
                team=project.team
        scores=data.get('scores')
        if not isinstance(scores,list) or len(scores)!=7 or any(v is not None and (not isinstance(v,(int,float)) or isinstance(v,bool) or not 0<=v<=100) for v in scores):raise ValidationError('论文分数无效。')
        for review in data.get('aiReviews',[]):
            if not isinstance(review,dict) or not valid_id(review.get('id')):raise ValidationError('AI 评阅标识无效。')
            try:run=AIRun.objects.filter(id=uuid.UUID(str(review.get('serverRunId'))),user=user,operation='paper-review').first()
            except ValueError:run=None
            existing=next((r for r in (old.payload.get('aiReviews',[]) if old else []) if equal(r,review)),None)
            if not existing and (not run or run.paper_id!=data['id'] or run.input_hash!=hashlib.sha256(str(review.get('input','')).encode()).hexdigest() or review.get('output')!=run.output or review.get('model')!=run.model):raise ValidationError('评阅记录需关联本论文、本账号及该次原文快照的真实模型调用。')
            if not existing:review.update(at=run.created_at.isoformat(),instruction=run.messages[0]['content'],provider='server-gateway',sourceHash=run.input_hash)
    if collection=='tasks':
        if user.role=='student' and (team or data.get('audience')=='school' or data.get('scope') in ['公开资料','校内资料','教师私有']):raise PermissionDenied('学生创建的任务仅供本人练习。')
        if user.role in ['mentor','admin'] and not team and data.get('audience')!='school':raise ValidationError('请为教学任务选择团队或全校可见范围。')
        for key in data.get('attachmentIds',[]):
            resource=reference(user,key,'resources')
            if user.role!='student' and key not in (old.payload.get('attachmentIds',[]) if old else []) and resource.owner_id!=user.id and resource.scope!='public':raise PermissionDenied('教学任务只能新关联本人资料或公共知识，不能转发他人的私人附件。')
    if collection=='teams':
        require_text(data,'name',240,False)
        for key in data.get('fileIds',[]):reference(user,key,'resources',owned=True)
        if old:
            for published in old.payload.get('messages',[]):
                if published.get('status')=='published' and not any(equal(published,message) for message in data.get('messages',[])):
                    raise ValidationError('已发布消息不能删除或改写，请创建新消息。')
            removed=set(old.payload.get('fileIds',[]))-set(data.get('fileIds',[]))
            if removed:
                attachments=Record.objects.exclude(scope='deleted').filter(collection='notifications',team=old).values_list('payload__attachmentIds',flat=True)
                if any(removed.intersection(ids or []) for ids in attachments):raise Conflict('已发布的团队通知仍引用此附件，不能移除关联。')
        for message in data.get('messages',[]):
            if not isinstance(message,dict) or not valid_id(message.get('id')):raise ValidationError('消息标识无效。')
            require_text(message,'title',240,False);require_text(message,'body',50000,False)
            if not isinstance(message.get('attachmentIds'),list) or not set(message['attachmentIds'])<=set(data.get('fileIds',[])):raise ValidationError('消息附件需来自团队文件。')
            published=next((m for m in (old.payload.get('messages',[]) if old else []) if m.get('id')==message['id'] and m.get('status')=='published'),None)
            if published and not equal(published,message):raise ValidationError('已发布消息不能改写，请创建新消息。')
            # Immutable published recipients describe the original delivery,
            # including members removed since publication. Only that unchanged
            # history may retain old IDs; drafts still require current members.
            if not isinstance(message.get('recipientIds'),list) or (not published and not set(message['recipientIds'])<={m.get('id') for m in data.get('members',[]) if isinstance(m,dict)}):raise ValidationError('消息收件成员无效。')
            if message.get('status')!='draft' and not any(equal(message,m) for m in (old.payload.get('messages',[]) if old else []) if m.get('status')=='published'):raise ValidationError('请通过发布按钮发布团队通知。')
    if collection in ['supervisionPlans','reminderDrafts']:
        target_students(user,data.get('studentIds' if collection=='supervisionPlans' else 'recipientIds'))
        if collection=='reminderDrafts':
            if data.get('channel')!='email':raise ValidationError('仅支持邮箱提醒。')
            if data.get('status')!='draft':raise ValidationError('通过发信接口处理队列状态。')
            require_text(data,'body',50000,False)
        else:
            for key in ['minWeeklySessions','maxInactiveDays']:
                value=data.get(key)
                if value is not None and (not isinstance(value,int) or isinstance(value,bool) or not 1<=value<=365):raise ValidationError('监督目标需为1–365整数或留空。')
    if collection in ['scoreRecords','usageRecords']:
        if user.role not in ['mentor','admin']:raise PermissionDenied('人工记录需要导师权限。')
        if collection=='scoreRecords' and data.get('submissionId'):
            submission=reference(user,data['submissionId'],'taskSubmissions')
            if submission.payload.get('personId')!=data.get('personId') or not editable(user,submission):raise PermissionDenied('成绩必须关联自己评阅的提交。')
        else:target_students(user,[data.get('personId')])
        require_text(data,'source',500,False)
        if collection=='scoreRecords':
            score,maximum=data.get('score'),data.get('maxScore')
            if any(not isinstance(v,(int,float)) or isinstance(v,bool) for v in [score,maximum]) or not 0<=score<=maximum or maximum<=0:raise ValidationError('成绩范围无效。')
    if collection=='taskSubmissions':
        if old:
            if old.owner_id==user.id and user.role!='admin' and not equal(data,old.payload):raise PermissionDenied('提交快照不可改写，请提交新版本。')
            if old.owner_id!=user.id and user.role!='admin':
                if user.role!='mentor' or not editable(user,old):raise PermissionDenied('只有任务导师可以评阅提交。')
                if data.get('status') not in ['reviewed','returned']:raise ValidationError('评阅状态无效。')
                require_text(data,'feedback',50000,False)
                frozen={k:v for k,v in data.items() if k not in ['feedback','status','reviewedAt']}
                before={k:v for k,v in old.payload.items() if k not in ['feedback','status','reviewedAt']}
                if not equal(frozen,before):raise PermissionDenied('导师只能修改反馈与评阅状态。')
        else:
            task=reference(user,data.get('taskId'),'tasks');project=reference(user,data.get('projectId'),'projects',owned=True)
            if project.payload.get('taskId')!=task.id:raise ValidationError('项目未关联此训练任务。')
            data['personId']=str(user.id);data['snapshot']=copy.deepcopy(project.payload);data['submittedAt']=timezone.now().isoformat();data['status']='submitted';data['feedback']=''
            papers=list(Record.objects.exclude(scope='deleted').filter(collection='papers',owner=user,payload__projectId=project.id))
            data['paperIds']=[p.id for p in papers]
            data['snapshot']['paperSnapshots']=[copy.deepcopy(p.payload) for p in papers]
            data['snapshot']['resourceIds']=list(dict.fromkeys(data['snapshot'].get('resourceIds',[])+[p.payload['fileId'] for p in papers]))
            data['version']=Record.objects.filter(collection=collection,owner=user,payload__taskId=task.id).count()+1
            team=task.team
    return data,team

@transaction.atomic
def save_workspace(user,changes,preferences):
    require_verified(user)
    if not isinstance(changes,dict) or any(k not in COLLECTIONS for k in changes):raise ValidationError('集合无效。')
    lock_workspace_resources(changes)
    versions={}
    order=['resources','teams','tasks','projects','papers','competitions','conversations','writingDrafts','supervisionPlans','reminderDrafts','taskSubmissions','scoreRecords','usageRecords','notifications']
    for collection in order:
        if not isinstance(changes.get(collection,[]),list) or len(changes.get(collection,[]))>2000:raise ValidationError('待保存记录列表无效。')
        for item in changes.get(collection,[]):
            if not isinstance(item,dict):raise ValidationError('记录格式无效。')
            key=item.get('id')
            if collection=='competitions' and item.get('projectId'):
                # Deletion/restoration uses the same project -> competition lock
                # order. Do this before locking an existing competition row.
                Record.objects.select_for_update(of=('self',)).filter(pk=item['projectId'],collection='projects').first()
            old=Record.objects.select_for_update(of=('self',)).select_related('team').filter(id=key).first()
            if old and (old.collection!=collection or not editable(user,old)):raise PermissionDenied('不能修改此记录。')
            if old and equal(item,old.payload):versions[collection+'/'+key]=old.revision;continue
            if old and item.get('_revision')!=old.revision:raise Conflict()
            old_files=set(old.payload.get('fileIds',[])) if old and collection=='teams' else set()
            data,team=validate_record(user,collection,item,old)
            scope=resource_scope(user,data) if collection=='resources' else 'private'
            if collection=='tasks' and data.get('audience')=='school' and user.role in ['mentor','admin']:scope='school'
            if old:
                old.payload=data;old.team=team if data.get('teamId') or collection=='taskSubmissions' else old.team;old.scope=scope;old.revision+=1;old.save();row=old
            else:row=Record.objects.create(id=key,collection=collection,owner=user,team=team,scope=scope,payload=data)
            versions[collection+'/'+key]=row.revision
            if collection=='resources':
                from .retrieval import invalidate_resource
                invalidate_resource(row)
            if collection=='teams':
                Record.objects.filter(id__in=data.get('fileIds',[]),owner=user,collection='resources').update(team=row)
                versions.update(clear_team_file_access(row,old_files-set(data.get('fileIds',[]))))
            Audit.objects.create(actor=user,action='save:'+collection,target=key)
    Workspace.objects.get_or_create(user=user)
    workspace=Workspace.objects.select_for_update().get(user=user)
    if isinstance(preferences,dict):
        if 'lastConversationId' in preferences:
            selected=preferences['lastConversationId']
            if not valid_id(selected):raise ValidationError('上次对话编号无效。')
            if not Record.objects.filter(pk=selected,collection='conversations',owner=user).exists():raise PermissionDenied('对话不存在或不属于当前账号。')
            workspace.preferences['lastConversationId']=selected
        weights=preferences.get('weights')
        if weights is not None:
            if not isinstance(weights,list) or len(weights)!=7 or any(not isinstance(v,(int,float)) or isinstance(v,bool) or v<0 for v in weights) or sum(weights)!=100:raise ValidationError('评价权重无效。')
            workspace.preferences['weights']=weights
        if isinstance(preferences.get('integritySettings'),dict):workspace.preferences['integritySettings']={'competitionPeriod':preferences['integritySettings'].get('competitionPeriod') is True}
        workspace.save()
    return versions
