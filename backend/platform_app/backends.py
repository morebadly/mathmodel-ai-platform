from django.contrib.auth.backends import ModelBackend
from .access import ADMIN_LOGINS,fixed_admin
from .models import User

class FixedAdminBackend(ModelBackend):
    def authenticate(self,request,username=None,password=None,**kwargs):
        alias=str(username or '').strip().lower()
        if alias not in ADMIN_LOGINS:return None
        user=User.objects.filter(admin_login=alias).first()
        if user and user.check_password(password or '') and fixed_admin(user):return user
        return None
