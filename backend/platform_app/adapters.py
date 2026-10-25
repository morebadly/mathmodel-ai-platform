from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
class AccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self,request,emailconfirmation):
        from urllib.parse import urlencode
        role='mentor' if emailconfirmation.email_address.user.requested_role=='mentor' else 'student'
        return settings.SITE_URL+'/?'+urlencode({'verify':emailconfirmation.key,'email':emailconfirmation.email_address.email})+'#login/'+role
