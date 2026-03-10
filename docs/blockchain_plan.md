# implementation_plan.md - Phase 16: Blockchain & Wallet Infrastructure

This phase introduces true blockchain and web3 wallet features to the AetherStore network, laying the foundation for a decentralized ledger of ATK token transactions.

## User Review Required
> [!IMPORTANT]
> A critical design decision is non-custodial vs custodial wallets. This plan proposes a **non-custodial** approach, which is the standard for Web3. This means AetherStore API nodes *do not* securely store users' private keys. When a user creates a wallet, the API will generate the mnemonic and return it to them *once*. Users must hold onto their mnemonics and use them to cryptographically sign transfers. Please confirm if this approach is preferred!

## Proposed Changes

### [Component] Wallet Crypto Core
#### [NEW] `apps/core/crypto_wallet.py`
- We will build the cryptographic foundation utilizing the user-provided BIP-39 wordlist:
  - `generate_mnemonic()`: Selects 12 entropy-secured words from [bip39_wordlist_mnemonics_english.txt](file:///c:/Users/stanl/Desktop/vscodeworkspace/pythonplayground/aetherstore/bip-39-wordlist/bip39_wordlist_mnemonics_english.txt).
  - `mnemonic_to_seed(mnemonic)`: Derives a secure cryptographic seed via PBKDF2 (HMAC-SHA512).
  - `derive_keypair(seed)`: Generates an Ed25519 private/public signing pair via `cryptography`.
  - `generate_address(public_key)`: Hashes the public key to generate a user-facing wallet address, prefixed with `ath1...` (e.g. `ath1xyz...`).

### [Component] Ledger & Transactions
#### [MODIFY] [apps/billing/models.py](file:///c:/Users/stanl/Desktop/vscodeworkspace/pythonplayground/aetherstore/apps/billing/models.py)
- Update [UserWallet](file:///c:/Users/stanl/Desktop/vscodeworkspace/pythonplayground/aetherstore/apps/billing/models.py#6-15) and [NodeWallet](file:///c:/Users/stanl/Desktop/vscodeworkspace/pythonplayground/aetherstore/apps/billing/models.py#17-26) models to use the new standard `ath1...` wallet addresses instead of generic DIDs and Node IDs.
- **[NEW Model] `LedgerTransaction`**: Represents peer-to-peer coin transfers on the network.
  - Fields: `tx_hash` (unique identifier derived from content), `sender_address`, `recipient_address`, `amount`, `signature`, `timestamp`, `status`.

### [Component] Blockchain API Endpoints
#### [MODIFY] [apps/billing/views.py](file:///c:/Users/stanl/Desktop/vscodeworkspace/pythonplayground/aetherstore/apps/billing/views.py)
- **`WalletCreateView`**: Endpoint to generate a new standard non-custodial wallet. Returning: `{ "mnemonic": "...", "private_key": "...", "public_key": "...", "address": "ath1..." }`. (The server drops the keys after returning this response).
- **`WalletTransferView`**: Endpoint for peer-to-peer token transfers. Accepts `{ "sender": "...", "recipient": "...", "amount": "...", "signature": "..." }`. The API will verify the Ed25519 cryptographic signature against the sender's public key before allowing the funds to move in the ledger.

### [Component] Storage Nodes
#### [MODIFY] [apps/p2p/storage_node.py](file:///c:/Users/stanl/Desktop/vscodeworkspace/pythonplayground/aetherstore/apps/p2p/storage_node.py)
- Update node startup logic. Nodes will optionally generate a BIP-39 mnemonic on first boot and derive an `ath1...` address to hold the mining rewards they receive from the payout calculator.

## Verification Plan

1. **Wallet Generation**: Call `/api/v1/wallet/generate/` to create an Aether wallet and ensure the mnemonic securely maps to the `ath1...` address.
2. **Non-Custodial Transfers**: Alice generates a P2P transaction, cryptographically signs the transfer payload using her raw private key locally, and submits the string signature to the API to send ATK to Bob.
3. **Ledger Integrity**: Verify that unsigned or poorly signed transactions are rejected off-chain before making it to the ledger.
