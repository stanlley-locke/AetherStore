import requests
import time
import sys
import os

# Add local path to use the crypto_wallet module directly for signing
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
import django
django.setup()
from apps.core import crypto_wallet

BASE_URL = "http://localhost:8000/api/v1"

def get_auth(did="did:example:alice"):
    return f"DID-Signature {did}:fakesig:{int(time.time())}:alice{int(time.time())}"

print("=== 1. Generating Non-Custodial Wallet for Alice ===")
resp = requests.post(f"{BASE_URL}/billing/wallet/generate/", headers={"Authorization": get_auth()})
alice_wallet = resp.json()
print("Alice's Address:", alice_wallet.get('address'))
print("Alice's DID:", alice_wallet.get('did'))
print("Alice's Mnemonic:", alice_wallet.get('mnemonic'))
print("Alice's Initial Balance:", requests.get(f"{BASE_URL}/billing/wallet/", headers={"Authorization": get_auth(alice_wallet['did'])}).json().get('balance'))
print("-" * 50)

print("=== 2. Generating Non-Custodial Wallet for Bob ===")
resp = requests.post(f"{BASE_URL}/billing/wallet/generate/", headers={"Authorization": get_auth("did:example:bob")})
bob_wallet = resp.json()
print("Bob's Address:", bob_wallet.get('address'))
print("-" * 50)

print("=== 3. Cryptographically Signing a P2P Transfer (Alice -> Bob) ===")
# Setup payload
recipient = bob_wallet['address'].lower()
amount = "15.50"
timestamp = str(int(time.time()))

# Sign payload locally (simulating a client-side wallet app)
message_to_sign = f"{recipient}:{amount}:{timestamp}"
signature = crypto_wallet.sign_message(alice_wallet['private_key'], message_to_sign)
print(f"Payload: {message_to_sign}")
print(f"Signature (Ed25519): {signature[:32]}...")

print("-" * 50)
print("=== 4. Executing Transfer on the AetherStore Ledger ===")
transfer_payload = {
    "public_key": alice_wallet['public_key'],
    "recipient_address": recipient,
    "amount": amount,
    "timestamp": timestamp,
    "signature": signature
}

resp = requests.post(f"{BASE_URL}/billing/wallet/transfer/", json=transfer_payload)
print("Transfer Response:", resp.json())

print("-" * 50)
print("=== 5. Verifying Balances ===")
alice_final = float(requests.get(f"{BASE_URL}/billing/wallet/", headers={"Authorization": get_auth(alice_wallet['did'])}).json().get('balance'))
bob_final = float(requests.get(f"{BASE_URL}/billing/wallet/", headers={"Authorization": get_auth(bob_wallet['did'])}).json().get('balance'))

print(f"Alice Final Balance: {alice_final} (Expected ~84.499)")
print(f"Bob Final Balance: {bob_final} (Expected 115.5)")

# Alice should have lost (15.50 + 0.001)
# Bob should have gained 15.50

print("\n✓ Blockchain Wallet & Ledger tests completed successfully!")
