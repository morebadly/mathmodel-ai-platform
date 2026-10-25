"""Stream authenticated originals in bounded chunks under ASGI as well as WSGI."""
from django.http import FileResponse

def protected_file(request,field,**kwargs):
    stream=field.open('rb');response=FileResponse(stream,**kwargs)
    if hasattr(request,'scope'):
        async def chunks():
            from asgiref.sync import sync_to_async
            try:
                while data:=await sync_to_async(stream.read,thread_sensitive=False)(65536):yield data
            finally:await sync_to_async(stream.close,thread_sensitive=False)()
        response.streaming_content=chunks()
    return response
