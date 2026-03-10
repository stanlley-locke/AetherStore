# apps/accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Extended User model with DID support"""
    did = models.CharField(max_length=255, unique=True, null=True, blank=True)
    is_network_admin = models.BooleanField(default=False, help_text='Grants access to the AetherNode Admin Console')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'auth_user'
        # Don't create new table, extend existing auth_user