"""Server-owned registration policy and the three separately provisioned admins."""
from django.contrib.auth.hashers import check_password
from .models import RegistrationPolicy

ADMIN_LOGINS=('admin01','admin02','admin03')
ADMIN_EMAILS={alias:alias+'@mathmodel.invalid' for alias in ADMIN_LOGINS}

def fixed_admin(user):
    return bool(user.is_active and user.role=='admin' and user.is_staff and user.is_superuser and user.admin_login in ADMIN_LOGINS)

def valid_mentor_key(value):
    if not isinstance(value,str) or not 12<=len(value)<=128:return False
    policy=RegistrationPolicy.objects.filter(pk='default').first()
    return bool(policy and check_password(value,policy.mentor_key_hash))

def reserved_email(email):return email.lower() in ADMIN_EMAILS.values()
