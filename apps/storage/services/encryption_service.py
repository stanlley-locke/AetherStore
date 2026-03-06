"""
Encryption Service for Storage Operations
Manages client-side encryption keys and operations
"""

from apps.core.crypto import ClientEncryption
from django.core.cache import cache
from django.conf import settings
import hashlib
import os


class EncryptionService:
    """Service for managing file encryption/decryption"""
    
    @staticmethod
    def get_user_salt(user_did: str) -> bytes:
        """Get or create salt for user"""
        salt_key = f'encryption_salt:{user_did}'
        salt = cache.get(salt_key)
        
        if not salt:
            salt = os.urandom(16)
            cache.set(salt_key, salt, timeout=None)
        
        return salt
    
    @staticmethod
    def encrypt_file(file_data: bytes, user_did: str, metadata: dict = None) -> dict:
        """
        Encrypt file data for storage
        
        Args:
            file_data: Raw file bytes
            user_did: User's DID for key derivation
            metadata: Optional metadata to include
            
        Returns:
            Dict with encrypted data and metadata
        """
        salt = EncryptionService.get_user_salt(user_did)
        
        # Create encryption instance with explicit salt
        encryption = ClientEncryption(password=f'{user_did}:{salt.hex()}', salt=salt)
        
        # Prepare metadata
        full_metadata = metadata or {}
        full_metadata['owner_did'] = user_did
        full_metadata['original_hash'] = hashlib.sha256(file_data).hexdigest()
        full_metadata['original_size'] = len(file_data)
        
        # Encrypt
        encrypted = encryption.encrypt(file_data, metadata=full_metadata)
        encrypted['key_hash'] = encryption.get_key_hash()
        encrypted['user_did'] = user_did  # Store user_did for decryption
        
        return encrypted
    
    @staticmethod
    def decrypt_file(encrypted_package: dict, user_did: str) -> bytes:
        """
        Decrypt file data for download
        
        Args:
            encrypted_package: Encrypted data package
            user_did: User's DID for key derivation
            
        Returns:
            Decrypted file bytes
        """
        # Get salt (must be same as encryption)
        salt = EncryptionService.get_user_salt(user_did)
        
        # Create encryption instance with SAME salt
        encryption = ClientEncryption(password=f'{user_did}:{salt.hex()}', salt=salt)
        
        # Decrypt
        return encryption.decrypt(encrypted_package)
    
    @staticmethod
    def verify_key(user_did: str, key_hash: str) -> bool:
        """Verify encryption key matches"""
        salt = EncryptionService.get_user_salt(user_did)
        encryption = ClientEncryption(password=f'{user_did}:{salt.hex()}', salt=salt)
        return encryption.get_key_hash() == key_hash
