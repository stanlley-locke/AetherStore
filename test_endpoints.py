import sys
sys.path.append('.')

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aetherstore.settings")

import django
django.setup()

from apps.p2p.ring import get_hash_ring

ring = get_hash_ring()
ring.invalidate()

content_hash = "833a12f9a71aaa2a42311af6d548263910371937bb4f7177eacadb1a69c3ce56"
total_shards = 5

shard_map = ring.get_all_nodes_for_object(content_hash, total_shards)
for i in range(total_shards):
    print(f"Shard {i}: {shard_map[i]}")

