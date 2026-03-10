"""
init_network_admin.py
=====================
Run this script ONCE from the project root to create the first AetherNode
Network Admin wallet and register it in the database.

Usage:
    python scripts/init_network_admin.py

Output:
    - Prints the 12-word BIP-39 mnemonic phrase (save it securely!)
    - Prints the wallet address (ath1...)
    - Prints the DID (did:aether:ath1...)
    - Sets is_network_admin=True for that DID in the database

Requirements:
    - Django configured (DJANGO_SETTINGS_MODULE must be set)
    - The aetherstore virtualenv active
"""

import os
import sys
import django

# ── Django Setup ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.core.crypto_wallet import generate_mnemonic, derive_keypair

User = get_user_model()


def main():
    print("\n" + "=" * 60)
    print("  AetherNode Network Admin Wallet Initializer")
    print("=" * 60)

    # Warn if admins already exist
    existing_admins = User.objects.filter(is_network_admin=True)
    if existing_admins.exists():
        print(f"\n[!] WARNING: {existing_admins.count()} existing admin(s) found:")
        for adm in existing_admins:
            print(f"    - {adm.did}")
        cont = input("\nDo you want to create an ADDITIONAL admin? (yes/no): ").strip().lower()
        if cont != 'yes':
            print("\nAborted. Existing admins unchanged.")
            return

    # Generate wallet using the SAME BIP-39 logic as the billing API
    print("\n[*] Generating new admin wallet using BIP-39 derivation...")
    mnemonic = generate_mnemonic()
    keys = derive_keypair(mnemonic)

    address = keys['address']
    did = keys['did']

    # Register in Django — use get_or_create so re-runs are safe
    user, created = User.objects.get_or_create(
        username=did,
        defaults={
            'did': did,
            'email': 'admin@aether.node',
            'is_network_admin': True,
            'is_staff': True,
        }
    )
    if not created:
        user.is_network_admin = True
        user.is_staff = True
        user.save(update_fields=['is_network_admin', 'is_staff'])

    print("\n" + "=" * 60)
    print("  ✅  ADMIN WALLET CREATED SUCCESSFULLY")
    print("=" * 60)
    print(f"\n  DID Address    : {did}")
    print(f"  Wallet Address : {address}")
    print("\n  ⚠️  RECOVERY PHRASE (store securely, never share!):\n")
    print(f"  {mnemonic}")
    print("\n" + "=" * 60)
    print("\n  Use this mnemonic to log in to the AetherNode Admin Portal.")
    print("  Navigate to /aethernode/login and paste the phrase above.")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
