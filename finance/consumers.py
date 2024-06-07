import json
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

# Create a global variable to store connected clients
connected_clients = []


class CashTransferConsumer(WebsocketConsumer):
    def connect(self):
        # Get the authenticated user (if any)
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            self.user = AnonymousUser()  

        # Add the client to the connected clients list
        connected_clients.append(self)
        self.accept()

    def disconnect(self, close_code):
        # Remove the client from the connected clients list
        connected_clients.remove(self)

    def receive(self, text_data):
        """Receive message from WebSocket client."""
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        # Do something with the message
        # ...

    def send_message(self, message):  # <-- Add 'self' here
        """Send message to all connected clients."""
        for client in connected_clients:
            async_to_sync(client.send)(text_data=json.dumps({
                'message': message,
                # Add other data as needed (e.g., transfer details)
            }))
