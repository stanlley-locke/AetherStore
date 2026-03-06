import sys
sys.path.append('.')

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aetherstore.settings")

import django
django.setup()

from apps.storage.models import StorageNode

deleted_count, _ = StorageNode.objects.filter(node_id__startswith='aetherNode').delete()
print(f"Deleted {deleted_count} stale nodes.")

# Make sure only node-1 through node-5 are active
for n in StorageNode.objects.all():
    print(f"Remaining active: {n.node_id}")

