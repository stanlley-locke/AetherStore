"""
Merkle DAG Implementation for Large File Handling
Enables chunked storage, verification, and deduplication
"""

import hashlib
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field


@dataclass
class ChunkMetadata:
    """Metadata for a single chunk"""
    index: int
    hash: str
    size: int
    encrypted_hash: Optional[str] = None


@dataclass
class MerkleDAG:
    """Complete Merkle DAG structure for a file"""
    root_hash: str
    total_size: int
    chunk_count: int
    chunk_size: int
    chunks: List[ChunkMetadata]
    tree: List[List[str]] = field(default_factory=list)
    algorithm: str = 'SHA-256'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage"""
        return {
            'root_hash': self.root_hash,
            'total_size': self.total_size,
            'chunk_count': self.chunk_count,
            'chunk_size': self.chunk_size,
            'chunks': [asdict(c) for c in self.chunks],
            'tree': self.tree,
            'algorithm': self.algorithm
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MerkleDAG':
        """Reconstruct from dictionary"""
        chunks = [ChunkMetadata(**c) for c in data['chunks']]
        return cls(
            root_hash=data['root_hash'],
            total_size=data['total_size'],
            chunk_count=data['chunk_count'],
            chunk_size=data['chunk_size'],
            chunks=chunks,
            tree=data.get('tree', []),
            algorithm=data.get('algorithm', 'SHA-256')
        )


class MerkleDAGBuilder:
    """Build and verify Merkle DAGs"""
    
    DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, chunk_size: int = None, algorithm: str = 'SHA-256'):
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.algorithm = algorithm
    
    def _hash(self, data: bytes) -> str:
        """Compute hash of data"""
        if self.algorithm == 'SHA-256':
            return hashlib.sha256(data).hexdigest()
        elif self.algorithm == 'SHA-512':
            return hashlib.sha512(data).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")
    
    def build(self, data: bytes, filename: str = None) -> MerkleDAG:
        """
        Build Merkle DAG from file data
        
        Args:
            data: File bytes
            filename: Optional filename for metadata
            
        Returns:
            MerkleDAG object
        """
        if len(data) == 0:
            raise ValueError("Cannot build Merkle DAG from empty data")
        
        # Split into chunks
        chunks_data = self._split_into_chunks(data)
        
        # Create chunk metadata
        chunks = []
        for i, chunk in enumerate(chunks_data):
            chunk_hash = self._hash(chunk)
            chunks.append(ChunkMetadata(
                index=i,
                hash=chunk_hash,
                size=len(chunk)
            ))
        
        # Build Merkle tree
        tree = self._build_tree([c.hash for c in chunks])
        
        # Get root hash
        root_hash = tree[-1][0] if tree and tree[-1] else None
        
        return MerkleDAG(
            root_hash=root_hash,
            total_size=len(data),
            chunk_count=len(chunks),
            chunk_size=self.chunk_size,
            chunks=chunks,
            tree=tree,
            algorithm=self.algorithm
        )
    
    def _split_into_chunks(self, data: bytes) -> List[bytes]:
        """Split data into fixed-size chunks"""
        chunks = []
        for i in range(0, len(data), self.chunk_size):
            chunks.append(data[i:i + self.chunk_size])
        return chunks
    
    def _build_tree(self, hashes: List[str]) -> List[List[str]]:
        """
        Build Merkle tree from leaf hashes
        
        Returns:
            List of levels, each containing list of hashes
        """
        if not hashes:
            return []
        
        tree = [hashes.copy()]
        current_level = hashes
        
        while len(current_level) > 1:
            # Pad if odd number
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])
            
            # Build next level
            next_level = []
            for i in range(0, len(current_level), 2):
                combined = current_level[i] + current_level[i + 1]
                parent_hash = self._hash(combined.encode('utf-8'))
                next_level.append(parent_hash)
            
            tree.append(next_level)
            current_level = next_level
        
        return tree
    
    def verify(self, dag: MerkleDAG, chunks: Dict[int, bytes]) -> bool:
        """
        Verify chunk integrity against Merkle root
        
        Args:
            dag: MerkleDAG with root hash
            chunks: Dict of chunk_index -> chunk_data
            
        Returns:
            True if verification passes
        """
        if len(chunks) != dag.chunk_count:
            return False
        
        # Verify each chunk hash
        for chunk_meta in dag.chunks:
            index = chunk_meta.index
            expected_hash = chunk_meta.hash
            
            if index not in chunks:
                return False
            
            actual_hash = self._hash(chunks[index])
            if actual_hash != expected_hash:
                return False
        
        # Rebuild tree and verify root
        leaf_hashes = [c.hash for c in sorted(dag.chunks, key=lambda x: x.index)]
        tree = self._build_tree(leaf_hashes)
        
        return tree[-1][0] == dag.root_hash if tree else False
    
    def get_proof(self, dag: MerkleDAG, chunk_index: int) -> List[Dict]:
        """
        Get Merkle proof for a specific chunk
        
        Args:
            dag: MerkleDAG
            chunk_index: Index of chunk to prove
            
        Returns:
            List of sibling hashes for proof
        """
        if chunk_index >= len(dag.chunks):
            return []
        
        proof = []
        index = chunk_index
        
        for level in dag.tree[:-1]:  # Exclude root
            # Determine sibling
            if index % 2 == 0:
                sibling_index = index + 1
                position = 'right'
            else:
                sibling_index = index - 1
                position = 'left'
            
            # Handle odd-length levels
            if sibling_index >= len(level):
                sibling_index = index
            
            proof.append({
                'hash': level[sibling_index],
                'position': position,
                'level': dag.tree.index(level)
            })
            
            # Move to parent index
            index = index // 2
        
        return proof
    
    def verify_proof(self, chunk_hash: str, proof: List[Dict], root_hash: str) -> bool:
        """
        Verify Merkle proof
        
        Args:
            chunk_hash: Hash of chunk to verify
            proof: Merkle proof from get_proof()
            root_hash: Expected root hash
            
        Returns:
            True if proof is valid
        """
        current_hash = chunk_hash
        
        for step in proof:
            sibling_hash = step['hash']
            
            if step['position'] == 'left':
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash
            
            current_hash = self._hash(combined.encode('utf-8'))
        
        return current_hash == root_hash
    
    def get_chunk(self, data: bytes, chunk_index: int) -> bytes:
        """Get specific chunk from data"""
        start = chunk_index * self.chunk_size
        end = start + self.chunk_size
        return data[start:end]
    
    def reassemble(self, chunks: Dict[int, bytes], total_size: int) -> bytes:
        """
        Reassemble file from chunks
        
        Args:
            chunks: Dict of chunk_index -> chunk_data
            total_size: Total file size
            
        Returns:
            Reassembled file data
        """
        if not chunks:
            return b''
        
        # Sort by index and concatenate
        sorted_chunks = [chunks[i] for i in range(max(chunks.keys()) + 1) if i in chunks]
        data = b''.join(sorted_chunks)
        
        # Trim to exact size
        return data[:total_size]
