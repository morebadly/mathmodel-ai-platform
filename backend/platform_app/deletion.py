"""Revision-checked document trash; original rows and files are retained."""
import copy
import json

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from .domain import (Conflict, SHARED_SCOPE, can_read, require_verified,
                     valid_id, validate_record, editable, clear_team_file_access)
from .models import Asset, Audit, ChatMessage, ExecutionJob, Record

COLLECTIONS = {'writingDrafts', 'papers', 'resources', 'projects', 'competitions', 'conversations'}
SINGLE_REFERENCES = {'fileId', 'projectId', 'competitionId', 'taskId'}
LIST_REFERENCES = {'resourceIds', 'attachmentIds', 'fileIds', 'paperIds'}
FILE_FIELDS = {'projects': 'resourceIds', 'tasks': 'attachmentIds', 'teams': 'fileIds'}


def manages(user, row):
    # A mentor's right to annotate a student's paper is not a deletion right.
    return row.owner_id == user.id or (
        user.role == 'admin' and row.collection == 'resources'
        and row.payload.get('scope') == SHARED_SCOPE
    )


def revision(request):
    value = request.data.get('revision')
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValidationError('请先同步文档，再执行回收站操作。')
    return value


def dependency_signature(row):
    fields = {
        'projects': ['resourceIds', 'taskId', 'teamId'],
        'papers': ['fileId', 'projectId', 'teamId'],
        'resources': ['libraryAssetIds'],
        'competitions': ['projectId', '_deletedCompanionProjectId', 'teamId', 'attachmentIds'],
    }.get(row.collection, ['teamId'])
    return json.dumps({field: row.payload.get(field) for field in fields}, sort_keys=True, ensure_ascii=True)


def lock_restore_dependencies(row):
    """Use workspace's resource -> team/task/project -> parent lock order."""
    resource_ids = set()
    if row.collection == 'resources':
        resource_ids.add(row.id)
        resource_ids.update(item.get('id') for item in row.payload.get('libraryAssetIds', []) if isinstance(item, dict) and valid_id(item.get('id')))
    if row.collection == 'projects':
        resource_ids.update(value for value in row.payload.get('resourceIds', []) if valid_id(value))
    if row.collection == 'competitions':
        resource_ids.update(value for value in row.payload.get('attachmentIds', []) if valid_id(value))
    if row.collection == 'papers' and valid_id(row.payload.get('fileId')):
        resource_ids.add(row.payload['fileId'])
    if resource_ids:
        list(Record.objects.select_for_update(of=('self',)).filter(collection='resources', pk__in=resource_ids).order_by('id').values_list('id', flat=True))
    # Resource teamId is ignored by validate_record; it cannot grant sharing.
    if row.collection != 'resources' and valid_id(row.payload.get('teamId')):
        Record.objects.select_for_update(of=('self',)).filter(collection='teams', pk=row.payload['teamId']).first()
    if row.collection == 'projects' and valid_id(row.payload.get('taskId')):
        Record.objects.select_for_update(of=('self',)).filter(collection='tasks', pk=row.payload['taskId']).first()
    if row.collection == 'papers' and valid_id(row.payload.get('projectId')):
        Record.objects.select_for_update(of=('self',)).filter(collection='projects', pk=row.payload['projectId']).first()


def locked_record(request, collection, key, restoring=False):
    require_verified(request.user)
    if collection not in COLLECTIONS or not valid_id(key):
        raise NotFound('文档不存在或无权操作。')
    project_key, candidate, signature = None, None, None
    if restoring or collection == 'competitions':
        candidate = Record.objects.filter(pk=key, collection=collection).first()
        if not candidate or not manages(request.user, candidate):
            raise NotFound('文档不存在或无权操作。')
        signature = dependency_signature(candidate)
    # The parser locks Asset before Record. Use the same order so an in-flight
    # parser can be cancelled without deadlocking the document's deletion.
    if collection == 'resources':
        Asset.objects.select_for_update().filter(record_id=key).first()
    if restoring:
        lock_restore_dependencies(candidate)
    if collection == 'competitions':
        project_key = candidate.payload.get('_deletedCompanionProjectId') or candidate.payload.get('projectId') or ''
        # Workspace saves lock projects before competitions. Match that order,
        # including when only a competition is being changed.
        if project_key:
            Record.objects.select_for_update(of=('self',)).filter(pk=project_key, collection='projects').first()
    row = Record.objects.select_for_update(of=('self',)).select_related('team').filter(pk=key, collection=collection).first()
    if not row or not manages(request.user, row):
        raise NotFound('文档不存在或无权操作。')
    if collection == 'competitions' and project_key != (row.payload.get('_deletedCompanionProjectId') or row.payload.get('projectId') or ''):
        raise Conflict('比赛关联在操作期间已变化，请同步后重试。')
    if restoring and dependency_signature(row) != signature:
        raise Conflict('文档关联在等待期间已变化，请刷新回收站后重试。')
    return row


def references(value, key):
    if isinstance(value, dict):
        for field, item in value.items():
            if field in SINGLE_REFERENCES and item == key:
                return True
            if field in LIST_REFERENCES and isinstance(item, list) and key in item:
                return True
            if isinstance(item, (dict, list)) and references(item, key):
                return True
    elif isinstance(value, list):
        return any(references(item, key) for item in value if isinstance(item, (dict, list)))
    return False


def require_unreferenced(row, companion=None):
    # Never disclose another user's private title or record identifier in an
    # error. Historical submissions and published messages retain their files.
    if row.collection == 'projects' and Record.objects.exclude(scope='deleted').filter(collection='competitions', payload__projectId=row.pk).exists():
        raise Conflict('此项目仍关联未回收的模拟竞赛，请先将比赛移入回收站；比赛回收会保留项目正文与附件。')
    rows = Record.objects.exclude(scope='deleted').exclude(pk=row.pk).exclude(collection='resources').only('id', 'collection', 'owner_id', 'payload')
    for other in rows:
        payload = other.payload
        if companion and other.id == companion.id and other.owner_id == row.owner_id:
            # Only this top-level organizational marker may be detached. A
            # submitted snapshot or another nested reference still blocks trash.
            payload = {key: value for key, value in payload.items() if key != 'competitionId'}
        if references(payload, row.pk):
            raise Conflict('此文档仍被项目、论文、任务、团队或提交记录引用，请先解除可编辑的关联；已提交的历史版本需保留。')
    if row.collection == 'resources':
        # Legacy library entries share deduplicated originals. Read only their
        # small source mapping, rather than loading every library body text.
        mappings = Record.objects.filter(collection='resources').exclude(scope='deleted').exclude(pk=row.pk).values_list('payload__libraryAssetIds', flat=True)
        if any(any(isinstance(item, dict) and item.get('id') == row.pk for item in (mapping or [])) for mapping in mappings):
            raise Conflict('此原件仍被公共知识条目引用，请先移除相关条目的可编辑关联或保留原件。')
        if any(row.pk in ids for ids in ChatMessage.objects.values_list('attachments', flat=True)):
            raise Conflict('此文件已作为聊天附件发送，需要保留会话历史，不能移入回收站。')
        if any(row.pk in ids for ids in ExecutionJob.objects.values_list('input_ids', flat=True)):
            raise Conflict('此文件被代码运行记录引用，需要保留运行依据，不能移入回收站。')


@api_view(['GET'])
def trash(request):
    require_verified(request.user)
    result = []
    for row in Record.objects.filter(scope='deleted', collection__in=COLLECTIONS).order_by('-updated_at'):
        if manages(request.user, row):
            result.append({'id': row.id, 'collection': row.collection,
                           'title': row.payload.get('title') or row.payload.get('name') or '未命名文档',
                           'deletedAt': row.payload.get('_deletedAt', ''), 'revision': row.revision})
    return Response({'records': result})


@api_view(['POST'])
@transaction.atomic
def remove(request, collection, key):
    expected = revision(request)
    row = locked_record(request, collection, key)
    if row.scope == 'deleted':
        if expected != row.payload.get('_deletedRevision'):
            raise Conflict()
        return Response({'deleted': True, 'id': row.id, 'collection': row.collection, 'revision': row.revision, 'duplicate': True})
    if not can_read(request.user, row):
        raise NotFound('文档不存在或无权操作。')
    if expected != row.revision:
        raise Conflict()
    companion = None
    if collection == 'competitions' and row.payload.get('projectId'):
        companion = Record.objects.filter(pk=row.payload['projectId'], collection='projects', owner=row.owner).first()
        if not companion or companion.scope == 'deleted':
            raise Conflict('配套建模项目不存在或仍在回收站，请先恢复项目后再回收比赛。')
        if companion.payload.get('competitionId') not in [None, '', row.id]:
            raise Conflict('配套项目已关联其他比赛，请同步并处理关联后重试。')
    require_unreferenced(row, companion)
    cancelled_parse = collection == 'resources' and Asset.objects.filter(record=row, parse_status__in=['pending', 'processing']).exists()
    row.payload = copy.deepcopy(row.payload)
    row.payload.update(_deletedAt=timezone.now().isoformat(), _deletedBy=str(request.user.id),
                       _deletedScope=row.scope, _deletedRevision=row.revision,
                       _deletedParseCancelled=cancelled_parse)
    if companion:
        row.payload['_deletedCompanionProjectId'] = companion.id
        if companion.payload.get('competitionId') == row.id:
            companion.payload = {field: value for field, value in companion.payload.items() if field != 'competitionId'}
            companion.revision += 1
            companion.save(update_fields=['payload', 'revision', 'updated_at'])
            Audit.objects.create(actor=request.user, action='competition-project-detach', target=companion.id)
    row.scope = 'deleted'
    row.revision += 1
    row.save(update_fields=['scope', 'payload', 'revision', 'updated_at'])
    if collection == 'resources':
        from .retrieval import invalidate_resource
        invalidate_resource(row)
        # A running parse must not rewrite metadata after deletion. Its result
        # checks this status and claim token before it can commit.
        Asset.objects.filter(record=row, parse_status__in=['pending', 'processing']).update(
            parse_status='cancelled', claimed_at=None, parse_error='文档已移入回收站，解析已取消。')
    Audit.objects.create(actor=request.user, action='trash:' + collection, target=key)
    return Response({'deleted': True, 'id': row.id, 'collection': row.collection, 'revision': row.revision, 'duplicate': False})


@api_view(['POST'])
@transaction.atomic
def restore(request, collection, key):
    expected = revision(request)
    row = locked_record(request, collection, key, restoring=True)
    if row.scope != 'deleted':
        if row.payload.get('_restoredFromRevision') == expected:
            return Response({'restored': True, 'id': row.id, 'collection': row.collection, 'revision': row.revision, 'duplicate': True})
        raise Conflict('文档状态已变化，请刷新回收站后重试。')
    if expected != row.revision:
        raise Conflict()
    original_scope = row.payload.get('_deletedScope')
    resume_parse = row.payload.get('_deletedParseCancelled') is True
    companion_key = row.payload.get('_deletedCompanionProjectId')
    companion = None
    if collection == 'competitions' and companion_key:
        companion = Record.objects.filter(pk=companion_key, collection='projects', owner=row.owner).first()
        if not companion or companion.scope == 'deleted' or not can_read(request.user, companion):
            raise Conflict('配套建模项目尚未恢复或权限已变化，请先恢复项目，再恢复比赛。')
        if companion.payload.get('competitionId') not in [None, '', row.id]:
            raise Conflict('配套项目已关联其他比赛，不能覆盖该关联；请先处理项目关联后重试。')
    if original_scope not in {'private', 'public', 'school', 'teacher'}:
        raise ValidationError('原文档分区信息缺失，请联系管理员恢复。')
    if collection == 'resources' and row.payload.get('chatRoomId'):
        from .chat import allowed_room
        allowed_room(request.user, row.payload['chatRoomId'])
    # Validate live dependencies again; e.g. a paper's original may itself have
    # subsequently entered the trash. Permission failures do not expose it.
    try:
        data, _ = validate_record(request.user, collection, row.payload, old=row)
        if collection == 'resources':
            from .domain import reference
            for attachment in data.get('libraryAssetIds', []):
                reference(request.user, attachment.get('id'), 'resources')
    except NotFound:
        raise Conflict('关联文档尚未恢复或权限已变化，请先恢复关联文档，再重试。')
    data['_restoredFromRevision'] = expected
    if companion:
        # Merge only the relationship into the latest locked project payload;
        # never restore a snapshot over notes edited after the competition left.
        companion.payload = {**companion.payload, 'competitionId': row.id}
        companion.revision += 1
        companion.save(update_fields=['payload', 'revision', 'updated_at'])
        Audit.objects.create(actor=request.user, action='competition-project-attach', target=companion.id)
    row.payload = data
    row.scope = original_scope
    row.revision += 1
    row.save(update_fields=['scope', 'payload', 'revision', 'updated_at'])
    if collection == 'resources':
        from .retrieval import invalidate_resource
        invalidate_resource(row)
        asset = Asset.objects.filter(record=row).first()
        if asset and resume_parse and asset.parse_status == 'cancelled':
            asset.parse_status = 'pending'
            asset.parse_error = ''
            asset.claimed_at = None
            asset.save(update_fields=['parse_status', 'parse_error', 'claimed_at'])
            row.payload.update(parseStatus='pending', parseWarning='')
            row.save(update_fields=['payload', 'updated_at'])
    Audit.objects.create(actor=request.user, action='restore:' + collection, target=key)
    return Response({'restored': True, 'id': row.id, 'collection': row.collection, 'revision': row.revision, 'duplicate': False})


@api_view(['POST'])
@transaction.atomic
def detach_file(request, collection, key):
    """Remove a parent link, keeping its original and immutable history intact."""
    require_verified(request.user)
    expected = revision(request)
    file_id = request.data.get('fileId')
    if collection not in FILE_FIELDS or not valid_id(key) or not valid_id(file_id):
        raise ValidationError('文件关联操作无效。')
    # Do not disclose this resource's content or existence. A parent owner may
    # also remove a stale link to a resource whose access was already revoked.
    Record.objects.select_for_update(of=('self',)).filter(pk=file_id, collection='resources').first()
    row = Record.objects.select_for_update(of=('self',)).select_related('team').filter(pk=key, collection=collection).first()
    if not row or row.scope == 'deleted' or not can_read(request.user, row) or not editable(request.user, row) or (row.owner_id != request.user.id and request.user.role != 'admin'):
        raise NotFound('记录不存在或无权操作。')
    field = FILE_FIELDS[collection]
    values = row.payload.get(field, [])
    prior = row.payload.get('_lastDetachedFile', {})
    if file_id not in values and prior == {'id': file_id, 'revision': expected} and row.revision == expected + 1:
        return Response({'detached': True, 'id': row.id, 'collection': collection, 'fileId': file_id, 'revision': row.revision, 'duplicate': True})
    if row.revision != expected:
        raise Conflict()
    if file_id not in values:
        raise ValidationError('该文件已不在此记录的附件列表中，请刷新页面。')
    if collection == 'teams':
        if any(message.get('status') == 'published' and file_id in message.get('attachmentIds', []) for message in row.payload.get('messages', [])):
            raise Conflict('此文件已被发布的团队通知引用，不能移除该关联；需要保留通知历史。')
        # A notification may remain after its message metadata changed elsewhere.
        notifications = Record.objects.exclude(scope='deleted').filter(collection='notifications', team=row).values_list('payload__attachmentIds', flat=True)
        if any(file_id in (ids or []) for ids in notifications):
            raise Conflict('此文件已被发布的团队通知引用，不能移除该关联；需要保留通知历史。')
    row.payload = copy.deepcopy(row.payload)
    row.payload[field] = [value for value in values if value != file_id]
    if collection == 'teams':
        for message in row.payload.get('messages', []):
            if message.get('status') != 'published':
                message['attachmentIds'] = [value for value in message.get('attachmentIds', []) if value != file_id]
        clear_team_file_access(row, [file_id])
    row.payload['_lastDetachedFile'] = {'id': file_id, 'revision': expected}
    row.revision += 1
    row.save(update_fields=['payload', 'revision', 'updated_at'])
    Audit.objects.create(actor=request.user, action='detach-file:' + collection, target=row.id)
    return Response({'detached': True, 'id': row.id, 'collection': collection, 'fileId': file_id, 'revision': row.revision, 'duplicate': False})
