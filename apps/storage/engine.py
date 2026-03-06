"""
Erasure Coding Engine with Streaming Support
Reed-Solomon encoding/decoding with memory-efficient streaming
Production-ready with fallback support
"""

import hashlib
from typing import List, Optional, Generator, BinaryIO, Dict, Tuple
from django.conf import settings
import io
import logging

logger = logging.getLogger(__name__)

# Try to import a Reed-Solomon library with fallback
RS_AVAILABLE = False
RS_IMPLEMENTATION = None

try:
    import reedsolomon

    # The PyPI reedsolomon package (0.0.3) does not expose a usable Encoder class.
    # Check for the expected API; if missing, fall back to reedsolo.
    if hasattr(reedsolomon, 'Encoder'):
        RS_AVAILABLE = True
        RS_IMPLEMENTATION = 'reedsolomon'
        logger.info("ReedSolomon library (reedsolomon) loaded successfully")
    else:
        raise ImportError("reedsolomon missing Encoder class")

except Exception as e:
    try:
        import reedsolo

        RS_AVAILABLE = True
        RS_IMPLEMENTATION = 'reedsolo'
        logger.info("ReedSolomon library (reedsolo) loaded successfully")
    except Exception as e2:
        RS_AVAILABLE = False
        logger.warning("No Reed-Solomon library available. Using basic sharding only.")
        logger.debug(f"ReedSolomon import errors: {e}; {e2}")


class _ReedSoloEncoder:
    """Simple Reed-Solomon wrapper using the `reedsolo` library."""

    def __init__(self, data_shards: int, parity_shards: int):
        from reedsolo import RSCodec

        self.data_shards = data_shards
        self.parity_shards = parity_shards
        self.total_shards = data_shards + parity_shards
        self.rs = RSCodec(nsym=parity_shards)

    def encode(self, shards: List[bytes]) -> List[bytes]:
        """Encode data shards into data+parity shards."""
        if not shards:
            return []

        shard_size = len(shards[0])
        # Ensure all data shards are same length
        for s in shards:
            if len(s) != shard_size:
                raise ValueError("All shards must be the same length")

        # Prepare parity shards (bytearrays for efficient assignment)
        parity_shards = [bytearray(shard_size) for _ in range(self.parity_shards)]

        # Encode per-column (per-byte across data shards)
        for pos in range(shard_size):
            column = bytes(shard[pos] for shard in shards)
            encoded = self.rs.encode(column)
            parity_bytes = encoded[-self.parity_shards:]
            for i, b in enumerate(parity_bytes):
                parity_shards[i][pos] = b

        return shards + [bytes(p) for p in parity_shards]

    def decode(self, shards: List[Optional[bytes]]):
        """Reconstruct missing shards in-place (mutates the list)."""
        # Determine shard length from available shards
        shard_size = max((len(s) for s in shards if s is not None), default=0)

        # Ensure we have a mutable buffer for each shard
        shards_buf: List[bytearray] = [
            bytearray(s) if s is not None else bytearray(shard_size)
            for s in shards
        ]

        missing_indices = [i for i, s in enumerate(shards) if s is None]
        if not missing_indices:
            # Nothing to recover
            return

        for pos in range(shard_size):
            column = bytearray(self.total_shards)
            for idx in range(self.total_shards):
                shard = shards_buf[idx]
                column[idx] = shard[pos] if pos < len(shard) else 0

            try:
                decoded_full = self.rs.decode(bytes(column), erase_pos=missing_indices)
                # Reedsolo returns tuple (message, message+ecc, errata_pos)
                decoded = decoded_full[0]
            except Exception as e:
                logger.debug(f"ReedSolo decode failed at pos {pos}: {e}")
                continue

            for mi in missing_indices:
                if mi < len(decoded):
                    shards_buf[mi][pos] = decoded[mi]

        # Write reconstructed shards back into the original list
        for idx in missing_indices:
            shards[idx] = bytes(shards_buf[idx])


class ErasureCodingEngine:
    """
    Reed-Solomon Erasure Coding with streaming support
    Falls back to simple sharding if ReedSolomon unavailable
    """

    def __init__(self, data_shards: int = None, parity_shards: int = None):
        self.data_shards = data_shards or getattr(settings, 'RS_DATA_SHARDS', 6)
        self.parity_shards = parity_shards or getattr(settings, 'RS_PARITY_SHARDS', 3)
        self.total_shards = self.data_shards + self.parity_shards

        # Initialize Reed-Solomon encoder
        self.rs = None
        if RS_AVAILABLE:
            try:
                if RS_IMPLEMENTATION == 'reedsolomon':
                    self.rs = reedsolomon.Encoder(self.data_shards, self.parity_shards)
                elif RS_IMPLEMENTATION == 'reedsolo':
                    self.rs = _ReedSoloEncoder(self.data_shards, self.parity_shards)
                logger.info(f"ReedSolomon initialized: {self.data_shards}+{self.parity_shards} ({RS_IMPLEMENTATION})")
            except Exception as e:
                logger.warning(f"Failed to initialize ReedSolomon: {e}")
                self.rs = None
    
    @property
    def has_erasure_coding(self) -> bool:
        """Check if full erasure coding is available"""
        return self.rs is not None
    
    def compute_content_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash of content"""
        return hashlib.sha256(data).hexdigest()
    
    def compute_content_hash_stream(self, file_stream: BinaryIO) -> str:
        """Compute SHA-256 hash from stream without loading into memory"""
        hasher = hashlib.sha256()
        
        while True:
            chunk = file_stream.read(8192)  # 8KB chunks
            if not chunk:
                break
            hasher.update(chunk)
        
        # Reset stream position
        file_stream.seek(0)
        return hasher.hexdigest()
    
    def compute_shard_hashes(self, shards: List[bytes]) -> Dict[int, str]:
        """Compute hashes for all shards"""
        return {
            i: hashlib.sha256(shard).hexdigest()
            for i, shard in enumerate(shards)
        }
    
    def encode(self, data: bytes) -> List[bytes]:
        """
        Encode data into shards
        Returns: [data_shard_0, ..., data_shard_n, parity_shard_0, ..., parity_shard_m]
        """
        original_size = len(data)
        
        # Handle empty data
        if original_size == 0:
            return [b'\x00'] * self.total_shards
        
        # Pad data to be divisible by data_shards
        padding_needed = (self.data_shards - (original_size % self.data_shards)) % self.data_shards
        if padding_needed:
            data += b'\x00' * padding_needed
        
        # Split into data shards
        shard_size = len(data) // self.data_shards
        shards = [
            data[i:i + shard_size]
            for i in range(0, len(data), shard_size)
        ]
        
        # Ensure we have exactly data_shards
        while len(shards) < self.data_shards:
            shards.append(b'\x00' * shard_size)
        
        # Generate parity shards if ReedSolomon available
        if self.rs is not None:
            try:
                # Encoder.encode() returns all shards (data + parity)
                all_shards = self.rs.encode(shards)
                return all_shards
            except Exception as e:
                logger.warning(f"ReedSolomon encode failed: {e}. Using basic sharding.")
        
        # Return data shards only (no parity)
        return shards
    
    def encode_stream(self, file_stream: BinaryIO, chunk_size: int = 1024 * 1024) -> Generator[Tuple[int, List[bytes]], None, None]:
        """
        Encode large file in chunks (memory efficient)
        Yields: (chunk_index, List of shards for each chunk)
        """
        buffer = b''
        chunk_index = 0
        
        while True:
            chunk = file_stream.read(chunk_size)
            if not chunk:
                # Process remaining buffer
                if buffer:
                    yield (chunk_index, self.encode(buffer))
                break
            
            buffer += chunk
            
            # Process when buffer is large enough
            if len(buffer) >= chunk_size:
                yield (chunk_index, self.encode(buffer))
                buffer = b''
                chunk_index += 1
    
    def decode(self, shards: List[Optional[bytes]]) -> bytes:
        """
        Decode shards back to original data
        shards can contain None for missing shards
        """
        # Count available shards
        available_count = sum(1 for s in shards if s is not None)
        
        if available_count < self.data_shards:
            raise Exception(
                f"Not enough shards to decode. Need {self.data_shards}, have {available_count}"
            )
        
        # If ReedSolomon available and we have all shards, try reconstruction
        if self.rs is not None and len(shards) == self.total_shards:
            try:
                # Create working copy
                shard_copy = list(shards)
                
                # Identify missing shards
                missing_indices = [i for i, s in enumerate(shards) if s is None]
                
                # Reconstruct missing shards
                if missing_indices:
                    self.rs.decode(shard_copy)
                
                # Join data shards only
                return b''.join(shard_copy[:self.data_shards])
                
            except Exception as e:
                logger.warning(f"ReedSolomon decode failed: {e}. Using available shards.")
        
        # Fallback: join available data shards
        available_shards = [s for s in shards[:self.data_shards] if s is not None]
        return b''.join(available_shards)
    
    def verify_shard(self, shard: bytes, expected_hash: str) -> bool:
        """Verify shard integrity"""
        actual_hash = hashlib.sha256(shard).hexdigest()
        return actual_hash == expected_hash
    
    def verify_shards(self, shards: List[bytes], expected_hashes: Dict[int, str]) -> Dict[int, bool]:
        """Verify multiple shards and return verification results"""
        return {
            i: self.verify_shard(shard, expected_hashes.get(i, ''))
            for i, shard in enumerate(shards)
        }
    
    def get_shard_size(self, data_size: int) -> int:
        """Calculate size of each shard for given data size"""
        if data_size == 0:
            return 0
        padding_needed = (self.data_shards - (data_size % self.data_shards)) % self.data_shards
        return (data_size + padding_needed) // self.data_shards
    
    def get_byte_range_shards(self, start_byte: int, end_byte: int, total_size: int) -> List[int]:
        """
        Determine which shards are needed for a byte range
        Useful for range requests without decoding entire file
        """
        shard_size = self.get_shard_size(total_size)
        
        if shard_size == 0:
            return list(range(self.data_shards))
        
        start_shard = start_byte // shard_size
        end_shard = end_byte // shard_size
        
        # Get shards in range
        shards_needed = list(range(start_shard, min(end_shard + 1, self.data_shards)))
        
        # Ensure we have enough shards to decode
        while len(shards_needed) < self.data_shards:
            next_shard = len(shards_needed)
            if next_shard < self.total_shards:
                shards_needed.append(next_shard)
            else:
                break
        
        return shards_needed[:self.data_shards]
    
    def get_recovery_threshold(self) -> int:
        """Get minimum number of shards needed for recovery"""
        return self.data_shards
    
    def get_redundancy_ratio(self) -> float:
        """Get redundancy ratio (parity/data)"""
        return self.parity_shards / self.data_shards if self.data_shards > 0 else 0
    
    def get_storage_overhead(self, data_size: int) -> int:
        """Calculate total storage size including parity"""
        shard_size = self.get_shard_size(data_size)
        return shard_size * self.total_shards
    
    def get_stats(self) -> Dict:
        """Get engine statistics"""
        return {
            'data_shards': self.data_shards,
            'parity_shards': self.parity_shards,
            'total_shards': self.total_shards,
            'has_erasure_coding': self.has_erasure_coding,
            'recovery_threshold': self.get_recovery_threshold(),
            'redundancy_ratio': self.get_redundancy_ratio(),
        }


class StreamingEncoder:
    """
    Memory-efficient streaming encoder for large files
    Encodes file in chunks to avoid loading entire file into memory
    """
    
    def __init__(self, engine: ErasureCodingEngine = None, chunk_size: int = 1024 * 1024):
        self.engine = engine or get_erasure_engine()
        self.chunk_size = chunk_size
        self.total_bytes = 0
        self.charts_encoded = 0
    
    def encode_file(self, file_path: str) -> Generator[Dict, None, None]:
        """
        Encode file from disk path
        Yields: Dict with chunk info and shards
        """
        with open(file_path, 'rb') as f:
            for chunk_index, shards in self.engine.encode_stream(f, self.chunk_size):
                self.charts_encoded += 1
                chunk_size = sum(len(s) for s in shards)
                self.total_bytes += chunk_size
                
                yield {
                    'chunk_index': chunk_index,
                    'shards': shards,
                    'shard_count': len(shards),
                    'chunk_size': chunk_size,
                    'total_encoded': self.total_bytes,
                }
    
    def encode_stream(self, file_stream: BinaryIO) -> Generator[Dict, None, None]:
        """
        Encode from file stream
        Yields: Dict with chunk info and shards
        """
        for chunk_index, shards in self.engine.encode_stream(file_stream, self.chunk_size):
            self.charts_encoded += 1
            chunk_size = sum(len(s) for s in shards)
            self.total_bytes += chunk_size
            
            yield {
                'chunk_index': chunk_index,
                'shards': shards,
                'shard_count': len(shards),
                'chunk_size': chunk_size,
                'total_encoded': self.total_bytes,
            }
    
    def get_stats(self) -> Dict:
        """Get encoding statistics"""
        return {
            'total_bytes': self.total_bytes,
            'chunks_encoded': self.charts_encoded,
            'chunk_size': self.chunk_size,
            'engine_stats': self.engine.get_stats(),
        }


# Singleton instance
_engine = None

def get_erasure_engine() -> ErasureCodingEngine:
    """Get singleton erasure coding engine"""
    global _engine
    if _engine is None:
        _engine = ErasureCodingEngine()
    return _engine


def reset_engine():
    """Reset engine singleton (useful for testing)"""
    global _engine
    _engine = None