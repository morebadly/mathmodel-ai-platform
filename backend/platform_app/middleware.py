from django.http import JsonResponse
class AccountBindingMiddleware:
    """Reject writes from a tab whose displayed account no longer owns the cookie session."""
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        path=request.path
        exempt=path.startswith('/api/auth/') and path!='/api/auth/session' and path!='/api/auth/logout'
        if path.startswith('/api/') and path not in ['/api/capabilities','/api/reminders/unsubscribe'] and not exempt:
            expected=request.headers.get('X-MM-Account','')
            writing=request.method not in ['GET','HEAD','OPTIONS']
            if expected and (not request.user.is_authenticated or expected!=str(request.user.pk)) or writing and request.user.is_authenticated and not expected:
                return JsonResponse({'error':{'message':'登录账号已变化或页面身份不匹配。请先导出当前草稿，再刷新核对账号。'}},status=409)
        return self.get_response(request)
