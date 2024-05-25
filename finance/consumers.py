from channels.generic.websocket import WebsocketConsumer
import json

class InvoiceNotificationConsumer(WebsocketConsumer):
    def connect(self):
        # Accept the connection (authentication can be added here if needed)
        self.accept()

    def receive(self, text_data):
        # Handle messages from the client (if any)
        pass 

    def invoice_created(self, event):
        # Send the invoice details to the client
        self.send(text_data=json.dumps({
            'type': 'invoice_created',
            'invoice': event['invoice']
        }))
