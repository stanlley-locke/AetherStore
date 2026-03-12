"""
Encryption Service for Storage Operations
Manages client-side encryption keys and operations
"""

from apps.core.crypto import ClientEncryption
from django.core.cache import cache
from django.conf import settings
import hashlib
import os
import base64


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
    def get_convergent_encryption(file_hash: str) -> ClientEncryption:
        """
        Create a ClientEncryption instance derived from the content hash.
        This enables global deduplication of encrypted data.
        """
        # derivation_seed is the file hash
        # salt is derived from the first 16 bytes of the hash
        salt = bytes.fromhex(file_hash[:32])
        return ClientEncryption(password=f"convergent:{file_hash}", salt=salt)

    @staticmethod
    def encrypt_file(file_data: bytes, user_did: str, metadata: dict = None, convergent: bool = False) -> dict:
        """
        Encrypt file data for storage
        
        Args:
            file_data: Raw file bytes
            user_did: User's DID for key derivation
            metadata: Optional metadata to include
            convergent: Whether to use convergent encryption (derived from content)
            
        Returns:
            Dict with encrypted data and metadata
        """
        if convergent:
            file_hash = hashlib.sha256(file_data).hexdigest()
            encryption = EncryptionService.get_convergent_encryption(file_hash)
            salt = encryption.salt
        else:
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
        encrypted['convergent'] = convergent
        
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
        if encrypted_package.get('convergent'):
            # For convergent encryption, we need the original hash (which is also the root hash in our system)
            # This should be in the metadata or we can use the root_hash if available
            original_hash = encrypted_package.get('metadata', {}).get('original_hash')
            if not original_hash:
                raise ValueError("Original hash missing from metadata for convergent decryption")
            encryption = EncryptionService.get_convergent_encryption(original_hash)
        else:
            # Get salt (must be same as encryption)
            salt = EncryptionService.get_user_salt(user_did)
            # Create encryption instance with SAME salt
            encryption = ClientEncryption(password=f'{user_did}:{salt.hex()}', salt=salt)
        
        # Decrypt
        return encryption.decrypt(encrypted_package)
    
    @staticmethod
    def get_encryption_instance(metadata: dict, owner_did: str, fallback_hash: str = None) -> ClientEncryption:
        """
        Get the correct ClientEncryption instance based on metadata.
        """
        if metadata.get('convergent'):
            original_hash = metadata.get('original_hash') or fallback_hash
            if not original_hash:
                raise ValueError("Original hash missing from metadata for convergent decryption")
            return EncryptionService.get_convergent_encryption(original_hash)
        else:
            salt_b64 = metadata.get('salt')
            if not salt_b64:
                raise ValueError("Salt missing from metadata")
            salt = base64.b64decode(salt_b64)
            return ClientEncryption(password=f'{owner_did}:{salt.hex()}', salt=salt)

    @staticmethod
    def verify_key(user_did: str, key_hash: str) -> bool:
        """Verify encryption key matches"""
        salt = EncryptionService.get_user_salt(user_did)
        encryption = ClientEncryption(password=f'{user_did}:{salt.hex()}', salt=salt)
        return encryption.get_key_hash() == key_hash
