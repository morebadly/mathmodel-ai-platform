from django.contrib import admin
from django.urls import path,re_path
from platform_app import views,auth_views,chat,grades,retrieval,media,execution,health,deletion
urlpatterns=[
    path('health/ready',health.ready),path('health',health.live),
    path('admin/',admin.site.urls),
    path('api/capabilities',views.capabilities),path('api/auth/session',auth_views.session),path('api/csrf',auth_views.session),path('api/auth/<str:mode>',auth_views.action),
    path('api/workspace',views.workspace),path('api/profile',views.profile),path('api/files',views.upload),path('api/files/<str:key>',views.download),path('api/usage/heartbeat',views.usage),
    path('api/records/trash',deletion.trash),path('api/records/<str:collection>/<str:key>/delete',deletion.remove),path('api/records/<str:collection>/<str:key>/restore',deletion.restore),
    path('api/records/<str:collection>/<str:key>/detach-file',deletion.detach_file),
    path('api/chat/rooms',chat.rooms),path('api/chat/rooms/<uuid:key>/messages',chat.messages),path('api/chat/rooms/<uuid:key>/read',chat.read),path('api/chat/rooms/<uuid:key>/files',chat.upload),
    path('api/teams/<str:team_id>/members/<uuid:user_id>/remove',chat.remove_member),
    path('api/grades/import',grades.import_grades),path('api/retrieval/search',retrieval.search),path('api/retrieval/index-tasks',retrieval.index_tasks),path('api/retrieval/index-tasks/<uuid:key>/cancel',retrieval.cancel_index),
    path('api/files/<str:key>/parse',media.status),
    path('api/execution/runtimes',execution.runtimes),path('api/execution/jobs',execution.jobs),path('api/execution/jobs/<uuid:key>',execution.job_detail),path('api/execution/artifacts/<uuid:key>',execution.artifact),
    path('api/reminders/<str:key>/send',views.send_reminder),path('api/mail-jobs',views.mail_jobs),path('api/teams/<str:key>/invite',views.invite),path('api/invitations/accept',views.accept_invite),path('api/teams/<str:key>/publish',views.publish),path('api/reminders/unsubscribe',views.unsubscribe),
    path('api/admin/accounts/<uuid:key>/role',views.account_role),path('api/admin/accounts/<uuid:key>/status',views.account_status),path('api/admin/readiness',views.readiness),path('api/ai/<str:operation>',views.ai),path('dev-mailbox/',views.dev_mailbox),path('health',lambda request:__import__('django.http',fromlist=['JsonResponse']).JsonResponse({'app':'MathModel AI','version':'2.0-django','mode':'django-local'})),
    path('',views.static_frontend),re_path(r'^(?P<path>.+)$',views.static_frontend)
]
