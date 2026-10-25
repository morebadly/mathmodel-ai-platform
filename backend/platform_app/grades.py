"""Atomic, source-attributed CSV grade import. No school data is fabricated."""
import csv,hashlib,io,math,json
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError,PermissionDenied
from .domain import require_verified,managed_users,Conflict
from .models import Record,Audit

COLUMNS=['email','assessment','assessmentDate','score','maxScore','source']

@api_view(['GET','POST'])
def import_grades(request):
    require_verified(request.user)
    if request.user.role not in ['mentor','admin']:raise PermissionDenied('只有导师或管理员可以导入成绩。')
    if request.method=='GET':
        response=HttpResponse('\ufeff'+','.join(COLUMNS)+'\r\n',content_type='text/csv; charset=utf-8');response['Content-Disposition']='attachment; filename="grades-template.csv"';return response
    raw=request.data.get('csv','');preview=request.data.get('preview',True)
    if not isinstance(raw,str) or len(raw)>1000000 or not isinstance(preview,bool):raise ValidationError('CSV或预检参数无效（上限1MB）。')
    reader=csv.DictReader(io.StringIO(raw.lstrip('\ufeff')),strict=True)
    if reader.fieldnames!=COLUMNS:raise ValidationError('列名及顺序必须为：'+','.join(COLUMNS))
    students={u.email.lower():u for u in managed_users(request.user).filter(role='student',is_active=True)};items=[];seen=set()
    try:
        for line,row in enumerate(reader,2):
            if line>1001:raise ValidationError('每次最多导入1000行。')
            if set(row)!=set(COLUMNS) or any(value is None for value in row.values()):raise ValidationError(f'第{line}行列数不正确。')
            email=row['email'].strip().lower();student=students.get(email)
            if not student:raise PermissionDenied(f'第{line}行邮箱不在你的授权学生范围内。')
            assessment=row['assessment'].strip();source=row['source'].strip()
            if not assessment or len(assessment)>240 or not source or len(source)>500:raise ValidationError(f'第{line}行考核名称或来源无效。')
            try:
                score=float(row['score']);maximum=float(row['maxScore']);date=timezone.make_aware(datetime.strptime(row['assessmentDate'].strip(),'%Y-%m-%d'))
            except (ValueError,TypeError):raise ValidationError(f'第{line}行成绩或日期无效（日期YYYY-MM-DD）。')
            if not all(math.isfinite(x) for x in [score,maximum]) or not 0<=score<=maximum or maximum<=0:raise ValidationError(f'第{line}行成绩范围无效。')
            key='grade_'+hashlib.sha256(json.dumps([str(request.user.id),str(student.id),assessment,date.isoformat(),source],ensure_ascii=False).encode()).hexdigest()
            if key in seen:raise ValidationError(f'第{line}行重复考核，请先整理同一学生的重复行。')
            seen.add(key);data={'id':key,'personId':str(student.id),'assessment':assessment,'assessmentDate':date.isoformat(),'score':score,'maxScore':maximum,'source':source,'createdAt':timezone.now().isoformat(),'importMethod':'csv'}
            items.append(data)
    except csv.Error:raise ValidationError('CSV引号或分隔格式无效。')
    if not items:raise ValidationError('CSV没有成绩数据，请先填写模板。')
    duplicates=0
    with transaction.atomic():
        # Membership and owner state are rechecked at commit time, not trusted from the preview.
        request.user.refresh_from_db();require_verified(request.user)
        if request.user.role not in ['mentor','admin']:raise PermissionDenied('导师权限已撤销。')
        allowed={str(u.id) for u in managed_users(request.user).filter(role='student',is_active=True)}
        for data in items:
            if data['personId'] not in allowed:raise PermissionDenied('学生关系已变化，请重新预检。')
            old=Record.objects.select_for_update().filter(pk=data['id']).first()
            if old:
                if old.owner_id!=request.user.id or old.collection!='scoreRecords' or any(old.payload.get(k)!=data[k] for k in ['personId','assessment','assessmentDate','score','maxScore','source']):raise Conflict('已存在不同成绩，未覆盖。请核对来源并人工处理。')
                duplicates+=1
            elif not preview:Record.objects.create(id=data['id'],owner=request.user,collection='scoreRecords',payload=data)
        if not preview:Audit.objects.create(actor=request.user,action='grade-import',target=hashlib.sha256(raw.encode()).hexdigest())
    return Response({'preview':preview,'rows':len(items),'created':0 if preview else len(items)-duplicates,'duplicates':duplicates,'students':len({d['personId'] for d in items}),'sourceRequired':True,'statistics':'成绩按考核/日期/来源区分；使用为会话次数和活跃天数，不代表专注时长或因果关系。'})
