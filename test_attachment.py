#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from projects.models import ChatMessage

# Check message 21
msg = ChatMessage.objects.filter(id=21).first()
if msg:
    print(f"Message 21 found:")
    print(f"  ID: {msg.id}")
    print(f"  Sender: {msg.sender}")
    print(f"  Message: {msg.message[:50]}")
    print(f"  Attachment: {msg.attachment}")
    print(f"  Has attachment: {bool(msg.attachment)}")
    if msg.attachment:
        print(f"  Attachment name: {msg.attachment.name}")
        if hasattr(msg.attachment, 'path'):
            print(f"  Attachment path: {msg.attachment.path}")
            print(f"  File exists: {os.path.exists(msg.attachment.path)}")
else:
    print("Message 21 not found")
    
# List all messages with attachments
print("\n\nAll messages with attachments:")
messages = ChatMessage.objects.filter(attachment__isnull=False).exclude(attachment='')
for msg in messages:
    print(f"  ID {msg.id}: {msg.attachment.name}")
