import sys
sys.path.append('.')

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aetherstore.settings")

import django
django.setup()

from apps.p2p.ring import get_hash_ring
from apps.storage.models import StorageNode

# Ensure we have 5 nodes active in the DB for the test if not already
for i in range(1, 6):
    StorageNode.objects.get_or_create(node_id=f"node-{i}", defaults={'endpoint': f"http://localhost:800{i}"})

ring = get_hash_ring()
ring.invalidate()

content_hash = "94947f834cec6ac7b1ae032424b8414d0f4f69dc9b8541ad202923ba9a163c07"
total_shards = 5

print("Distribution:")
shard_map = ring.get_all_nodes_for_object(content_hash, total_shards)
for i in range(total_shards):
    nodes = [n[0] for n in shard_map[i]]
    print(f"Shard {i}: {nodes}")

