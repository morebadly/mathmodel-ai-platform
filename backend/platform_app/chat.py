"""Persistent relationship-scoped chat; WebSocket delivery is a notification, DB is authoritative."""
import uuid
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q,Max
from django.http import FileResponse
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view,parser_classes
from rest_framework.parsers import MultiPartParser,FormParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from .models import User,Record,Membership,Invitation,ChatRoom,ChatParticipant,ChatMessage,Asset,Audit
from .domain import verified,require_verified

def related(a,b):
    if a.id==b.id or not verified(a) or not verified(b):return False
    teams=Record.objects.filter(Q(owner=a)|Q(memberships__user=a),collection='teams').select_related('owner').distinct()
    return any(team.owner.role in ['mentor','admin'] and verified(team.owner) and (team.owner_id==b.id or Membership.objects.filter(team=team,user=b).exists()) for team in teams)

def room_members(room):
    if room.team_id:
        team=Record.objects.select_related('owner').filter(pk=room.team_id,collection='teams').first()
        if not team or team.owner.role not in ['mentor','admin'] or not verified(team.owner):return []
        return list(User.objects.filter(Q(id=team.owner_id)|Q(id__in=Membership.objects.filter(team=team).values('user_id'))))
    return list(User.objects.filter(chat_participations__room=room))

def can_access(user,room):
    if not user or not user.is_authenticated or not verified(user):return False
    members=room_members(room)
    if room.team_id:return any(u.id==user.id and verified(u) for u in members)
    return len(members)==2 and any(u.id==user.id for u in members) and related(members[0],members[1])

def allowed_room(user,key):
    try:room=ChatRoom.objects.select_related('team').filter(pk=key).first()
    except (ValueError,__import__('django.core.exceptions',fromlist=['ValidationError']).ValidationError):room=None
    if not room or not can_access(user,room):raise NotFound('会话不存在或已失去成员权限。')
    return room

def message_json(message):
    return {'id':message.id,'roomId':str(message.room_id),'senderId':str(message.sender_id),'senderName':message.sender.display_name or '成员','clientId':str(message.client_id),'body':message.body,'attachments':[{'id':a,'name':Record.objects.filter(pk=a).values_list('payload__name',flat=True).first() or '文件'} for a in message.attachments],'createdAt':message.created_at.isoformat()}

def notify(room,message=None):
    layer=get_channel_layer()
    if not layer:return
    targets=set(u.id for u in room_members(room))|set(ChatParticipant.objects.filter(room=room).values_list('user_id',flat=True))
    for uid in targets:
        async_to_sync(layer.group_send)('chat.user.'+str(uid),{'type':'chat.event','room_id':str(room.id),'message_id':message.id if message else None})

@api_view(['GET','POST'])
def rooms(request):
    require_verified(request.user)
    if request.method=='POST':
        if request.data.get('teamId'):
            team=Record.objects.select_related('owner').filter(pk=request.data['teamId'],collection='teams').first()
            if not team or not (team.owner_id==request.user.id or Membership.objects.filter(team=team,user=request.user).exists()):raise PermissionDenied('只能进入自己团队的会话。')
            if team.owner.role not in ['mentor','admin'] or not verified(team.owner):raise PermissionDenied('团队导师权限已失效。')
            room,_=ChatRoom.objects.get_or_create(key='team:'+team.id,defaults={'team':team,'title':team.payload.get('name','团队聊天')[:160],'created_by':team.owner})
        else:
            try:peer=User.objects.filter(pk=request.data.get('peerId')).first()
            except (ValueError,__import__('django.core.exceptions',fromlist=['ValidationError']).ValidationError):peer=None
            if not peer or not related(request.user,peer):raise PermissionDenied('只能与有有效导师关系的成员发起私聊。')
            key='direct:'+':'.join(sorted([str(request.user.id),str(peer.id)]))
            with transaction.atomic():
                room,_=ChatRoom.objects.get_or_create(key=key,defaults={'title':'导师与学生私聊','created_by':request.user})
                for u in [request.user,peer]:ChatParticipant.objects.get_or_create(room=room,user=u)
        for u in room_members(room):ChatParticipant.objects.get_or_create(room=room,user=u)
        return Response({'room':room_json(room,request.user)},status=201)
    result=[]
    for room in ChatRoom.objects.select_related('team').order_by('-updated_at'):
        if can_access(request.user,room):result.append(room_json(room,request.user))
    teams=Record.objects.filter(Q(owner=request.user)|Q(memberships__user=request.user),collection='teams').distinct()
    candidate_ids=set(teams.values_list('owner_id',flat=True))|set(Membership.objects.filter(team__in=teams).values_list('user_id',flat=True))
    contacts=[{'id':str(u.id),'name':u.display_name or '成员','role':u.role} for u in User.objects.filter(id__in=candidate_ids).exclude(pk=request.user.pk) if related(request.user,u)]
    return Response({'rooms':result,'contacts':contacts})

def room_json(room,user):
    participant,_=ChatParticipant.objects.get_or_create(room=room,user=user)
    latest=room.messages.aggregate(last=Max('id'))['last'] or 0
    return {'id':str(room.id),'title':room.title,'teamId':room.team_id,'members':[{'id':str(u.id),'name':u.display_name or '成员'} for u in room_members(room) if verified(u)],'lastRead':participant.last_read,'lastId':latest,'unread':room.messages.filter(id__gt=participant.last_read).exclude(sender=user).count()}

@api_view(['GET','POST'])
def messages(request,key):
    require_verified(request.user);room=allowed_room(request.user,key)
    if request.method=='GET':
        try:after=max(0,int(request.query_params.get('after','0')))
        except ValueError:raise ValidationError('历史游标无效。')
        rows=list(room.messages.select_related('sender').filter(id__gt=after).order_by('id')[:200])
        return Response({'messages':[message_json(m) for m in rows],'cursor':rows[-1].id if rows else after,'hasMore':bool(rows and room.messages.filter(id__gt=rows[-1].id).exists())})
    body=request.data.get('body','');attachments=request.data.get('attachmentIds',[])
    if not isinstance(body,str) or len(body)>12000 or not isinstance(attachments,list) or len(attachments)>5 or len(set(str(a) for a in attachments))!=len(attachments):raise ValidationError('消息长度或附件格式无效。')
    if not body.strip() and not attachments:raise ValidationError('消息与附件不能同时为空。')
    try:client_id=uuid.UUID(str(request.data.get('clientId')))
    except ValueError:raise ValidationError('消息需携带有效的去重标识。')
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        room=allowed_room(request.user,key)
        existing=ChatMessage.objects.filter(room=room,sender=request.user,client_id=client_id).first()
        if existing:
            if existing.body!=body.strip() or existing.attachments!=attachments:raise ValidationError('同一去重标识不能对应不同内容。')
            return Response({'message':message_json(existing),'duplicate':True})
        for rid in attachments:
            row=Record.objects.select_for_update(of=('self',)).exclude(scope='deleted').filter(pk=rid,collection='resources',owner=request.user,payload__chatRoomId=str(room.id)).first()
            if not row or not Asset.objects.filter(record=row).exists():raise PermissionDenied('附件必须由本人上传到当前会话。')
        if room.messages.filter(sender=request.user,created_at__gte=timezone.now()-__import__('datetime').timedelta(minutes=1)).count()>=60:raise ValidationError('发送过于频繁，请稍后重试。')
        message=ChatMessage.objects.create(room=room,sender=request.user,client_id=client_id,body=body.strip(),attachments=attachments);room.save(update_fields=['updated_at'])
        ChatParticipant.objects.get_or_create(room=room,user=request.user)
        Audit.objects.create(actor=request.user,action='chat-send',target=str(room.id))
        transaction.on_commit(lambda:notify(room,message))
    return Response({'message':message_json(message),'duplicate':False},status=201)

@api_view(['POST'])
def read(request,key):
    require_verified(request.user);room=allowed_room(request.user,key)
    cursor=request.data.get('cursor')
    if not isinstance(cursor,int) or isinstance(cursor,bool) or cursor<0 or cursor>(room.messages.aggregate(last=Max('id'))['last'] or 0):raise ValidationError('已读游标无效。')
    participant,_=ChatParticipant.objects.get_or_create(room=room,user=request.user)
    ChatParticipant.objects.filter(pk=participant.pk,last_read__lt=cursor).update(last_read=cursor)
    return Response({'read':max(cursor,participant.last_read)})

@api_view(['POST'])
@parser_classes([MultiPartParser,FormParser])
def upload(request,key):
    require_verified(request.user);room=allowed_room(request.user,key)
    file=request.FILES.get('file')
    if not file or not 0<file.size<=settings.MAX_FILE_BYTES:raise ValidationError('请选择50MB以内的非空附件。')
    import hashlib,mimetypes
    from pathlib import Path
    try:upload_id=uuid.UUID(str(request.data.get('clientId')))
    except ValueError:raise ValidationError('文件上传需携带去重标识。')
    name=Path(file.name.replace('\\','/')).name[:240];rid='chatfile_'+hashlib.sha256((str(room.id)+str(request.user.id)+str(upload_id)).encode()).hexdigest();sha=hashlib.sha256()
    for chunk in file.chunks():sha.update(chunk)
    file.seek(0);mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
    payload={'id':rid,'name':name,'kind':'attachment','scope':'个人资料','category':'','text':'','tags':'','description':'会话专属附件','chatRoomId':str(room.id),'size':file.size,'type':mime,'createdAt':timezone.now().isoformat(),'parseStatus':'saved_only'}
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        room=allowed_room(request.user,key)
        existing=Asset.objects.filter(record_id=rid,record__owner=request.user).first()
        if existing:
            if existing.record.scope=='deleted':raise NotFound('此附件已移入回收站，请先恢复或重新选择文件上传。')
            if existing.sha256!=sha.hexdigest() or existing.original_name!=name:raise ValidationError('同一上传标识不能对应不同文件。')
            return Response({'file':{'id':rid,'name':name},'duplicate':True})
        row=Record.objects.create(id=rid,collection='resources',owner=request.user,payload=payload)
        Asset.objects.create(record=row,file=file,original_name=name,size=file.size,sha256=sha.hexdigest(),content_type=mime,parse_status='saved_only')
    return Response({'file':{'id':rid,'name':name}},status=201)

@api_view(['POST'])
def remove_member(request,team_id,user_id):
    require_verified(request.user);team=Record.objects.filter(pk=team_id,collection='teams').first()
    if not team or not (team.owner_id==request.user.id or request.user.role=='admin'):raise PermissionDenied('只有团队导师或管理员能移除成员。')
    if str(team.owner_id)==str(user_id):raise ValidationError('不能移除团队所有者。')
    with transaction.atomic():
        member=User.objects.select_for_update().filter(pk=user_id).first()
        if not member:raise NotFound('成员不存在。')
        team=Record.objects.select_for_update().get(pk=team_id)
        if team.owner_id!=request.user.id and request.user.role!='admin':raise PermissionDenied('团队权限已变化。')
        Membership.objects.filter(team=team,user=member).delete()
        for invitation in Invitation.objects.select_for_update().filter(team=team,email__iexact=member.email):
            invitation.version+=1;invitation.issued_at=None;invitation.accepted_at=None;invitation.save()
        team.payload['members']=[m for m in team.payload.get('members',[]) if str(m.get('accountId',''))!=str(user_id) and str(m.get('identifier','')).lower()!=member.email.lower()]
        team.revision+=1;team.save()
        for room in ChatRoom.objects.filter(Q(team=team)|Q(participants__user=member)).distinct():transaction.on_commit(lambda r=room:notify(r))
        Audit.objects.create(actor=request.user,action='team-remove-member',target=str(team.id)+':'+str(member.id))
    return Response({'removed':True})
