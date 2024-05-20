import json
from channels.generic.websocket import AsyncWebsocketConsumer, AsyncJsonWebsocketConsumer

class InventoryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.branch_id = self.scope['url_route']['kwargs']['branch_id']
        self.group_name = f'branch_{self.branch_id}'
        print(self.branch_id)

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
    
    async def disconnect(self, close_code):  
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
    )


    # async def stock_update(self, event):
    #     await self.send(text_data=json.dumps({
    #         'product': event['product'],
    #         'quantity': event['quantity']
    #     }))

