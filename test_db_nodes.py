import sys
sys.path.append('.')

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aetherstore.settings")

import django
django.setup()

from apps.storage.models import StorageNode

nodes = StorageNode.objects.filter(is_active=True)
print("Active Nodes in DB:")
for n in nodes:
    print(f"ID: {n.node_id}, Endpoint: {n.endpoint}")

