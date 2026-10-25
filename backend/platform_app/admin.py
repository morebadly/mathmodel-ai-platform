from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin.forms import AdminAuthenticationForm
from django import forms
from .access import fixed_admin
from .models import User,Record,Membership,Invitation,Asset,Usage,MailJob,Audit
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering=['email'];list_display=['email','display_name','role','requested_role','is_active'];search_fields=['email','display_name']
    fieldsets=((None,{'fields':('email','password','display_name','role','requested_role','cohort','reminder_consent','track_usage')}),('管理权限',{'fields':('is_active','is_staff','is_superuser','groups','user_permissions')}))
    add_fieldsets=((None,{'classes':('wide',),'fields':('email','password1','password2','display_name','role')}),)
    def get_readonly_fields(self,request,obj=None):
        return ('email','role','is_staff','is_superuser') if obj and obj.admin_login else ()
    def get_form(self,request,obj=None,**kwargs):
        form=super().get_form(request,obj,**kwargs)
        if 'role' in form.base_fields:form.base_fields['role'].choices=[choice for choice in User._meta.get_field('role').choices if choice[0]!='admin']
        return form
    def has_delete_permission(self,request,obj=None):
        return False if obj and obj.admin_login else super().has_delete_permission(request,obj)
    actions=None
admin.site.register([Record,Membership,Invitation,Asset,Usage,MailJob,Audit])

class FixedAdminAuthenticationForm(AdminAuthenticationForm):
    username=forms.CharField(label='管理账号',widget=forms.TextInput(attrs={'autofocus':True,'autocomplete':'username'}))
    def confirm_login_allowed(self,user):
        super().confirm_login_allowed(user)
        if not fixed_admin(user):raise forms.ValidationError('请使用三个固定管理账号之一。')

admin.site.login_form=FixedAdminAuthenticationForm
admin.site.has_permission=lambda request:request.user.is_authenticated and fixed_admin(request.user)
