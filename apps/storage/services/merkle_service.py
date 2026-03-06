"""
Merkle DAG Service for Storage Operations
"""

from apps.core.merkle import MerkleDAGBuilder, MerkleDAG, ChunkMetadata
from typing import Dict, List, Optional


class MerkleService:
    """Service for Merkle DAG operations"""
    
    @staticmethod
    def build_merkle_dag(file_data: bytes, chunk_size: int = 10 * 1024 * 1024) -> MerkleDAG:
        """
        Build Merkle DAG from file data
        
        Args:
            file_data: File bytes (plaintext)
            chunk_size: Size of each chunk (default 10MB)
            
        Returns:
            MerkleDAG object
        """
        builder = MerkleDAGBuilder(chunk_size=chunk_size)
        return builder.build(file_data)
    
    @staticmethod
    def verify_chunks(dag: MerkleDAG, chunks: Dict[int, bytes]) -> bool:
        """
        Verify chunk integrity
        
        Args:
            dag: MerkleDAG with root hash
            chunks: Dict of chunk_index -> chunk_data
            
        Returns:
            True if all chunks verified
        """
        builder = MerkleDAGBuilder(chunk_size=dag.chunk_size)
        return builder.verify(dag, chunks)
    
    @staticmethod
    def get_chunk_proof(dag: MerkleDAG, chunk_index: int) -> List[Dict]:
        """
        Get Merkle proof for a chunk
        
        Args:
            dag: MerkleDAG
            chunk_index: Index of chunk
            
        Returns:
            Merkle proof
        """
        builder = MerkleDAGBuilder(chunk_size=dag.chunk_size)
        return builder.get_proof(dag, chunk_index)
    
    @staticmethod
    def verify_chunk_proof(chunk_hash: str, proof: List[Dict], root_hash: str) -> bool:
        """
        Verify Merkle proof for a chunk
        
        Args:
            chunk_hash: Hash of chunk
            proof: Merkle proof
            root_hash: Expected root hash
            
        Returns:
            True if proof valid
        """
        builder = MerkleDAGBuilder()
        return builder.verify_proof(chunk_hash, proof, root_hash)
    
    @staticmethod
    def reassemble_file(chunks: Dict[int, bytes], total_size: int) -> bytes:
        """
        Reassemble file from chunks
        
        Args:
            chunks: Dict of chunk_index -> chunk_data
            total_size: Total file size
            
        Returns:
            Reassembled file bytes
        """
        builder = MerkleDAGBuilder()
        return builder.reassemble(chunks, total_size)
    
    @staticmethod
    def get_chunk_from_data(file_data: bytes, chunk_index: int, chunk_size: int = 10 * 1024 * 1024) -> bytes:
        """Get specific chunk from data"""
        builder = MerkleDAGBuilder(chunk_size=chunk_size)
        return builder.get_chunk(file_data, chunk_index)
