import asyncio
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.sessions.models import Session
from django.utils import timezone
from .models import User,ChatRoom,ChatMessage
from .domain import verified
from .chat import can_access,message_json

class ChatConsumer(AsyncJsonWebsocketConsumer):
    @database_sync_to_async
    def valid_session(self):
        user=User.objects.filter(pk=self.uid).first()
        session=Session.objects.filter(session_key=self.session_key,expire_date__gt=timezone.now()).first()
        data=session.get_decoded() if session else {}
        return bool(user and verified(user) and str(data.get('_auth_user_id'))==str(user.id) and data.get('_auth_user_hash')==user.get_session_auth_hash())
    async def connect(self):
        user=self.scope.get('user');expected=parse_qs(self.scope.get('query_string',b'').decode(errors='replace')).get('account',[''])[0]
        if not user or not user.is_authenticated or expected!=str(user.id):await self.close(code=4401);return
        self.uid=user.id;self.session_key=self.scope['session'].session_key
        if not await self.valid_session():await self.close(code=4401);return
        self.group='chat.user.'+str(user.id);await self.channel_layer.group_add(self.group,self.channel_name);await self.accept()
        await self.send_json({'type':'connected','accountId':str(user.id)});self.heartbeat=asyncio.create_task(self.check_connection())
    async def disconnect(self,code):
        if hasattr(self,'heartbeat'):self.heartbeat.cancel()
        if hasattr(self,'group'):await self.channel_layer.group_discard(self.group,self.channel_name)
    async def check_connection(self):
        try:
            while True:
                await asyncio.sleep(15)
                if not await self.valid_session():await self.close(code=4401);return
                await self.send_json({'type':'heartbeat'})
        except asyncio.CancelledError:pass
    async def receive_json(self,content,**kwargs):
        if not await self.valid_session():await self.close(code=4401);return
        if isinstance(content,dict) and content.get('type')=='ping':await self.send_json({'type':'pong'})
    @database_sync_to_async
    def event_payload(self,event):
        user=User.objects.get(pk=self.uid);room=ChatRoom.objects.filter(pk=event['room_id']).first()
        if not room or not can_access(user,room):return {'type':'revoked','roomId':event['room_id']}
        message=ChatMessage.objects.select_related('sender').filter(pk=event.get('message_id'),room=room).first() if event.get('message_id') else None
        return {'type':'message','message':message_json(message)} if message else {'type':'rooms_changed'}
    async def chat_event(self,event):
        if not await self.valid_session():await self.close(code=4401);return
        await self.send_json(await self.event_payload(event))
