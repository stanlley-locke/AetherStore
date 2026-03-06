import sys
sys.path.append('.')
from apps.storage.engine import _ReedSoloEncoder

data = b"Hello, World!" * 10
# pad to a multiple of data shards, say 6
padding = (6 - (len(data) % 6)) % 6
padded = data + b'\x00' * padding

shard_size = len(padded) // 6
shards = [padded[i:i+shard_size] for i in range(0, len(padded), shard_size)]
encoder = _ReedSoloEncoder(6, 3)

encoded_shards = encoder.encode(shards)
print(f"Encoded shards: {len(encoded_shards)}, len: {len(encoded_shards[0])}")

# Let's drop a parity and a data shard
encoded_shards[1] = None
encoded_shards[7] = None

encoder.decode(encoded_shards)

decoded = b"".join(encoded_shards[:6])
print(f"Decoded len: {len(decoded)}")
print(f"Match: {decoded == padded}")

