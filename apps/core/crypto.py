"""
Client-Side Encryption Module
Zero-knowledge encryption before data leaves client
Uses AES-256-GCM for authenticated encryption
"""

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import os
import hashlib
import base64
import json
from typing import Dict, Optional


class ClientEncryption:
    """
    Client-side encryption for zero-knowledge storage
    
    Features:
    - AES-256-GCM authenticated encryption
    - PBKDF2 key derivation from password
    - Key backup/restore functionality
    """
    
    SALT_SIZE = 16
    NONCE_SIZE = 12
    KEY_SIZE = 32
    ITERATIONS = 100000
    
    def __init__(self, password: str = None, key: bytes = None, salt: bytes = None):
        """
        Initialize encryption instance
        
        Args:
            password: User password for key derivation
            key: Raw 32-byte encryption key (alternative to password)
            salt: Salt for key derivation (generated if not provided)
        """
        if key:
            if len(key) != self.KEY_SIZE:
                raise ValueError(f"Key must be {self.KEY_SIZE} bytes for AES-256")
            self.key = key
            self.salt = salt
        elif password:
            self.salt = salt or os.urandom(self.SALT_SIZE)
            self.key = self._derive_key(password, self.salt)
        else:
            raise ValueError("Must provide either password or key")
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive 32-byte key from password using PBKDF2-HMAC-SHA256"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def encrypt(self, data: bytes, metadata: Dict = None) -> Dict:
        """Encrypt data with authenticated encryption

        Args:
            data: Raw bytes to encrypt
            metadata: Optional metadata to include

        Returns:
            Dict with encrypted_data, nonce, salt, auth_tag, metadata
        """
        # Generate random nonce
        nonce = os.urandom(self.NONCE_SIZE)

        # Create AES-GCM cipher
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.GCM(nonce),
            backend=default_backend()
        )

        # Encrypt
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()

        # Store combined payload as: nonce || ciphertext || auth_tag
        combined = nonce + ciphertext + encryptor.tag

        return {
            # Preserve backward-compatible fields, but ensure the encrypted_data
            # contains everything needed to decrypt even if metadata is missing.
            'encrypted_data': base64.b64encode(combined).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'salt': base64.b64encode(self.salt).decode('utf-8'),
            'auth_tag': base64.b64encode(encryptor.tag).decode('utf-8'),
            'metadata': metadata or {},
            'algorithm': 'AES-256-GCM',
            'iterations': self.ITERATIONS
        }
    
    def decrypt(self, encrypted_package: Dict) -> bytes:
        """Decrypt data from encrypted package

        Args:
            encrypted_package: Dict from encrypt() method

        Returns:
            Decrypted bytes
        """
        # Decode the encrypted blob (expected to be base64)
        encrypted_blob = base64.b64decode(encrypted_package['encrypted_data'])

        # Derive key if salt provided (must match encryption time salt)
        if 'salt' in encrypted_package and hasattr(self, 'password'):
            salt = base64.b64decode(encrypted_package['salt'])
            iterations = encrypted_package.get('iterations', self.ITERATIONS)
            self.key = self._derive_key_with_iterations(self.password, salt, iterations)

        # Determine nonce/auth_tag and ciphertext
        nonce = None
        auth_tag = None
        ciphertext = None

        if 'nonce' in encrypted_package and 'auth_tag' in encrypted_package:
            try:
                nonce = base64.b64decode(encrypted_package['nonce'])
                auth_tag = base64.b64decode(encrypted_package['auth_tag'])
            except Exception as e:
                raise ValueError(f"Invalid nonce/auth_tag encoding: {e}")

        # If we have explicit nonce/auth_tag, assume ciphertext is the rest
        if nonce is not None and auth_tag is not None:
            # If the encrypted_blob includes nonce+tag (legacy combined format), strip it
            if (len(encrypted_blob) >= self.NONCE_SIZE + len(auth_tag) and
                    encrypted_blob.startswith(nonce) and
                    encrypted_blob.endswith(auth_tag)):
                ciphertext = encrypted_blob[self.NONCE_SIZE:-len(auth_tag)]
            else:
                ciphertext = encrypted_blob
        else:
            # Try to recover nonce/auth_tag from the combined payload
            if len(encrypted_blob) < (self.NONCE_SIZE + 16):
                raise ValueError("Missing nonce/auth_tag and encrypted data too short to recover")

            nonce = encrypted_blob[: self.NONCE_SIZE]
            auth_tag = encrypted_blob[-16:]
            ciphertext = encrypted_blob[self.NONCE_SIZE:-16]

        # Basic validation
        if not (8 <= len(nonce) <= 128):
            raise ValueError(f"Invalid nonce length: {len(nonce)}")
        if len(auth_tag) not in (12, 13, 14, 15, 16):
            raise ValueError(f"Invalid auth_tag length: {len(auth_tag)}")

        # Create cipher and decrypt
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.GCM(nonce, auth_tag),
            backend=default_backend()
        )

        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        return plaintext
    
    def _derive_key_with_iterations(self, password: str, salt: bytes, iterations: int) -> bytes:
        """Derive key with custom iteration count"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def get_key_hash(self) -> str:
        """Get hash of encryption key for identification (not the key itself)"""
        return hashlib.sha256(self.key).hexdigest()[:16]
    
    @classmethod
    def get_user_salt(cls, user_did: str) -> bytes:
        """Get or create a cached salt for a given user DID."""
        from django.core.cache import cache

        salt_key = f'encryption_salt:{user_did}'
        salt = cache.get(salt_key)

        if not salt:
            salt = os.urandom(cls.SALT_SIZE)
            cache.set(salt_key, salt, timeout=None)

        return salt

    @classmethod
    def for_user(cls, user_did: str) -> "ClientEncryption":
        """Create a ClientEncryption instance for a given user DID."""
        salt = cls.get_user_salt(user_did)
        return cls(password=f'{user_did}:{salt.hex()}', salt=salt)

    def export_key(self, password: str) -> str:
        """
        Export encrypted key for backup
        
        Args:
            password: Password to encrypt the key
            
        Returns:
            JSON string with encrypted key
        """
        # Derive backup key from password
        backup_salt = os.urandom(self.SALT_SIZE)
        backup_key = self._derive_key(password, backup_salt)
        
        # Encrypt the actual key
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = Cipher(
            algorithms.AES(backup_key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_key = encryptor.update(self.key) + encryptor.finalize()
        
        return json.dumps({
            'encrypted_key': base64.b64encode(encrypted_key).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'auth_tag': base64.b64encode(encryptor.tag).decode('utf-8'),
            'salt': base64.b64encode(backup_salt).decode('utf-8'),
            'iterations': self.ITERATIONS
        })
    
    @classmethod
    def import_key(cls, encrypted_json: str, password: str) -> 'ClientEncryption':
        """
        Import encrypted key from backup
        
        Args:
            encrypted_json: JSON from export_key()
            password: Password to decrypt
            
        Returns:
            ClientEncryption instance
        """
        data = json.loads(encrypted_json)
        
        # Derive backup key from password
        salt = base64.b64decode(data['salt'])
        iterations = data.get('iterations', cls.ITERATIONS)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=cls.KEY_SIZE,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        backup_key = kdf.derive(password.encode())
        
        # Decrypt the actual key
        cipher = Cipher(
            algorithms.AES(backup_key),
            modes.GCM(
                base64.b64decode(data['nonce']),
                base64.b64decode(data['auth_tag'])
            ),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        key = decryptor.update(base64.b64decode(data['encrypted_key'])) + decryptor.finalize()
        
        return cls(key=key, salt=salt)


# Convenience functions
def encrypt_file(file_: bytes, password: str, metadata: Dict = None) -> Dict:
    """Encrypt file data with password"""
    encryption = ClientEncryption(password=password)
    return encryption.encrypt(file_, metadata)


def decrypt_file(encrypted_package: Dict, password: str) -> bytes:
    """Decrypt file data with password"""
    encryption = ClientEncryption(password=password)
    return encryption.decrypt(encrypted_package)