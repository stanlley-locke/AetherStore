# AetherStore Whitepaper: A Decentralized Future for Storage & Communication

## 1. Abstract
AetherStore is a unified peer-to-peer (P2P) platform designed to solve the critical vulnerabilities of centralized cloud storage and messaging. By combining Reed-Solomon Erasure Coding, Content-Addressable hashing, and Kademlia-based Distributed Hash Tables (DHT), AetherStore provides a resilient infrastructure where data is sharded across the network, encrypted end-to-end, and accessible even during central server failure.

## 2. Introduction
The modern internet relies on centralized silos (AWS, Google, Meta) which represent single points of failure and surveillance. AetherStore moves the internet's "base layer" back to the edge, utilizing the spare capacity of individual nodes to form a globally distributed storage engine and messaging relay.

## 3. Decentralized Storage Architecture
AetherStore does not store files. It stores **shards**.

### 3.1 Erasure Coding (Reed-Solomon)
Every file uploaded to AetherStore is split into $k$ data shards and $m$ parity shards. This allows for $(n, k)$ recovery, where the original file can be perfectly reconstructed as long as any $k$ shards out of $n$ are available.
*   **Default configuration**: 3 data shards + 2 parity shards.
*   **Resilience**: A file survives even if 40% of the hosting nodes go offline simultaneously.

### 3.2 Content-Addressable Hashing
Files are indexed by their SHA-256 hash, not by filename. This ensures "Content Integrity"—if a single bit changes, the identity of the file changes. This also enables global deduplication, saving massive amounts of network bandwidth and storage space.

## 4. Decentralized Identity (DID-Signature)
AetherStore uses a "Self-Sovereign Identity" model. Users are identified by DIDs (Decentralized Identifiers). Authentication is performed via cryptographic signatures (`DID-Signature`) included in every request header, eliminating the need for passwords and central login servers.

## 5. End-to-End Encrypted Messaging
Messaging in AetherStore is built on the same decentralized foundation as storage.

### 5.1 Hybrid Storage Model
*   **Active Layer (DHT)**: Encrypted message envelopes are stored in a Kademlia DHT. Nodes mathematically closest to the recipient's DID become the "mailbox nodes."
*   **Persistence Layer (DB)**: Local databases act as backups.
*   **Recovery**: The protocol supports "Self-Healing." If a message is lost in the database, the client automatically recovers the encrypted envelope from the P2P network.

### 5.2 Encryption
All communications utilize AES-256-GCM encryption with authenticated tags. The server never sees the plaintext; keys are held exclusively by the end-users.

## 6. Incentives & Reputation
AetherStore operates a "Proof-of-Storage" incentive model.
*   **Billing (ATK Tokens)**: Users pay a micro-fee for storage and messaging.
*   **Reputation**: Storage nodes earn tokens by maintaining high availability. The "Auditor" worker periodically pings nodes and verifies shard integrity. Nodes that fail frequently are penalized and eventually pruned from the network routing table.

## 7. Hybrid Design: Performance vs. Resilience
AetherStore employs a "Tracker-Peer" hybrid model:
1.  **Tracker (Django)**: Handles metadata indexing, billing orchestrations, and high-speed searching.
2.  **Peers (Storage Nodes)**: Handle the actual binary data and DHT routing.

This design allows for the speed of a centralized web app while maintaining the un-stoppable nature of a decentralized network. If the Tracker fails, the P2P nodes can still find and relay shards to each other.

## 8. Conclusion
AetherStore is more than a storage bucket; it is a blueprint for a resilient, user-owned internet. By decentralizing both the storage of static assets and the routing of real-time communication, AetherStore provides a robust alternative to "Big Tech" infrastructure.
