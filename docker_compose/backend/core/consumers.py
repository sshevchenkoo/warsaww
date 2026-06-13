import json
from channels.generic.websocket import AsyncWebsocketConsumer


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Simple WebSocket — whatever comes from one client
    is broadcast to everyone else in the same room.
    Verifies that the Redis channel layer works.
    """

    async def connect(self):
        self.room_name = "test_room"
        self.room_group_name = f"chat_{self.room_name}"

        # Join the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "system",
            "message": "Connected to WebSocket. Redis is working!",
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message", "")

        # Broadcast to everyone in the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": event["message"],
        }))
