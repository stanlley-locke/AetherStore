/**
 * AetherStore API Service
 * Handles all communication with the Django backend.
 * Uses DID-Signature auth: DID-Signature did:example:id:fakesig:{timestamp}:{nonce}
 */
import axios from 'axios';

export const BASE_URL = '/api/v1';

//  DID Auth Header
export function getDIDAuthHeader(did: string | null): string {
  if (!did) return '';
  const ts = Math.floor(Date.now() / 1000);
  const nonce = `${did.replace(/[^a-z0-9]/gi, '')}${ts}${Math.random().toString(36).slice(2)}`;
  return `DID-Signature ${did}:fakesig:${ts}:${nonce}`;
}

//  Axios instance with dynamic auth 
export function createAuthenticatedClient(did: string | null) {
  const client = axios.create({ baseURL: BASE_URL });
  client.interceptors.request.use((config) => {
    const header = getDIDAuthHeader(did);
    if (header) {
      config.headers['Authorization'] = header;
    }
    return config;
  });
  return client;
}

//  Storage / Objects ─

export interface AetherObject {
  id: string;
  name?: string;
  filename?: string;
  bucket_name?: string;
  size: number;
  mime_type: string;
  created_at: string;
  is_deleted?: boolean;
  root_hash?: string;
}

export interface ObjectsResponse {
  objects: AetherObject[];
  total: number;
  page: number;
  page_size: number;
}

export const storageApi = {
  /** List objects (files). Excludes deleted by default. */
  listObjects: (client: ReturnType<typeof createAuthenticatedClient>, params: { page?: number; page_size?: number; sort?: string; deleted?: boolean } = {}) =>
    client.get<ObjectsResponse>('/storage/objects/', { params: { page: 1, page_size: 50, sort: '-created_at', ...params } }),

  /** Upload a file to a bucket */
  upload: (client: ReturnType<typeof createAuthenticatedClient>, bucket: string, file: File, onProgress?: (p: number) => void) => {
    const form = new FormData();
    form.append('file', file);
    return client.post(`/storage/upload/${bucket}/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    });
  },

  /** Get stream URL for a file */
  streamUrl: (objectId: string) => `${BASE_URL}/storage/stream/${objectId}/`,

  /** Download a file (async) */
  startDownload: (client: ReturnType<typeof createAuthenticatedClient>, objectId: string) =>
    client.get(`/storage/download/${objectId}/`),

  /** Soft-delete a file */
  deleteObject: (client: ReturnType<typeof createAuthenticatedClient>, objectId: string) =>
    client.delete(`/storage/object/${objectId}/`),

  /** Restore a soft-deleted file */
  restoreObject: (client: ReturnType<typeof createAuthenticatedClient>, objectId: string) =>
    client.post(`/storage/object/${objectId}/`),

  /** List deleted objects (trash) */
  listTrash: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<ObjectsResponse>('/storage/objects/', { params: { deleted: true, sort: '-created_at' } }),

  /** IPNS: List all name records */
  listNames: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get('/storage/name/'),

  /** IPNS: Publish a name record */
  publishName: (client: ReturnType<typeof createAuthenticatedClient>, name: string, objectId: string) =>
    client.post('/storage/name/', { name, object_id: objectId }),

  /** IPNS: Resolve a name */
  resolveName: (name: string) => `${BASE_URL}/storage/resolve/${name}/`,

  /** Generate Public Presigned URL */
  generatePresignedUrl: (client: ReturnType<typeof createAuthenticatedClient>, objectId: string, ttl: number = 604800) =>
    client.post(`/storage/object/${objectId}/presigned/`, { ttl }),

  /** Get File Info for a Public URL */
  getPresignedInfo: (token: string) =>
    axios.get(`${BASE_URL}/storage/download/presigned/${token}/info/`),
};

//  Messaging 

export interface Conversation {
  id: string;
  name: string;
  conversation_id?: string;
  participants?: string[];
  latest_message?: {
    id: string;
    body: string;
    sender_did: string;
    created_at: string;
  } | null;
  unread_count?: number;
}

export interface InboxResponse {
  conversations: Array<{
    conversation_id: string;
    conversation_name: string;
    latest_message: { id: string; body: string; sender_did: string; created_at: string } | null;
  }>;
}

export const messagingApi = {
  /** Get inbox (all conversations) */
  getInbox: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<InboxResponse>('/messaging/inbox/'),

  /** Get DHT inbox (Shard Network) */
  getDHTInbox: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<InboxResponse>('/messaging/inbox/dht/'),

  /** Create a new conversation */
  createConversation: (client: ReturnType<typeof createAuthenticatedClient>, participants: string[], name: string) =>
    client.post<{ id: string; name: string }>('/messaging/conversations/', { participants, name }),

  /** Send a message */
  sendMessage: (client: ReturnType<typeof createAuthenticatedClient>, conversationId: string, body: string, attachmentId?: string) =>
    client.post(`/messaging/conversations/${conversationId}/send/`, { body, type: attachmentId ? 'attachment' : 'text', attachment_id: attachmentId }),

  /** Decrypt and read a message */
  decryptMessage: (client: ReturnType<typeof createAuthenticatedClient>, conversationId: string, messageId: string) =>
    client.get<{ plaintext: string; source: string }>(`/messaging/conversations/${conversationId}/messages/${messageId}/decrypt/`),

  /** Get detailed conversation info (members, etc) */
  getConversation: (client: ReturnType<typeof createAuthenticatedClient>, conversationId: string) =>
    client.get<any>(`/messaging/conversations/${conversationId}/`),
};

//  Billing / Wallet 

export interface WalletBalance {
  did: string;
  balance: number;
  recent_transactions: Array<{
    id: string;
    type: string;
    amount: number;
    description: string;
    date: string;
  }>;
}

export const walletApi = {
  /** Get wallet balance and recent transactions */
  getBalance: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<WalletBalance>('/billing/wallet/'),

  /** Deposit funds (fiat gateway simulation) */
  deposit: (client: ReturnType<typeof createAuthenticatedClient>, amount: string) =>
    client.post('/billing/deposit/', { amount }),

  /** Generate a new non-custodial wallet (returns mnemonic + keys) */
  generateWallet: () =>
    axios.post(`${BASE_URL}/billing/wallet/generate/`),

  /** Recover wallet from mnemonic */
  recoverWallet: (mnemonic: string) =>
    axios.post(`${BASE_URL}/billing/wallet/recover/`, { mnemonic }),

  /** Cryptographic P2P transfer */
  transfer: (client: ReturnType<typeof createAuthenticatedClient>, payload: { public_key: string; recipient_address: string; amount: string; timestamp: string; signature: string }) =>
    client.post('/billing/wallet/transfer/', payload),

  /** Resolve Wallet Address to DID */
  resolveWalletToDid: (client: ReturnType<typeof createAuthenticatedClient>, address: string) =>
    client.get<{ address: string; did: string }>(`/billing/wallet/resolve/${address}/`),
};

//  AetherNode Console (Miners & Admins) 

export interface StorageNode {
  node_id: string;
  endpoint: string;
  is_active: boolean;
  uptime_pct: number;
  used_bytes: number;
  capacity_bytes: number;
  reputation: number;
  last_heartbeat: string;
  latency_ms?: number;
  dht_peers?: number;
}

export interface FleetResponse {
  fleet_count: number;
  total_capacity_bytes: number;
  total_used_bytes: number;
  nodes: StorageNode[];
}

export interface MiningReward {
  node_id: string;
  amount: number;
  type: string;
  timestamp: string;
}

export interface EarningsResponse {
  total_earned: number;
  avg_reward: number;
  reward_count: number;
  recent_history: MiningReward[];
}

export interface TreasuryStats {
  atk_circulating_supply: number;
  user_wallets_total: number;
  node_earnings_unclaimed: number;
  global_storage_consumption_bytes: number;
  total_active_objects: number;
  active_network_nodes: number;
}

export interface AdminStatusResponse {
  did: string | null;
  is_network_admin: boolean;
  username: string;
}

export const aetherNodeApi = {
  /** Miner: Get fleet status */
  getFleet: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<FleetResponse>('/storage/miner/fleet/'),

  /** Miner: Get mining earnings */
  getEarnings: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<EarningsResponse>('/storage/miner/earnings/'),

  /** Miner: Claim a node */
  claimNode: (client: ReturnType<typeof createAuthenticatedClient>, nodeId: string, endpoint?: string) =>
    client.post('/storage/miner/claim/', { node_id: nodeId, endpoint }),

  /** Check if current user is a network admin */
  getAdminStatus: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<AdminStatusResponse>('/p2p/admin/status/'),

  /** Admin: Get network parameters */
  getParameters: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<Record<string, any>>('/p2p/admin/parameters/'),

  /** Admin: Update network parameters */
  updateParameters: (client: ReturnType<typeof createAuthenticatedClient>, params: Record<string, any>) =>
    client.patch('/p2p/admin/parameters/', params),

  /** Admin: Get treasury and global stats */
  getTreasuryStats: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<TreasuryStats>('/p2p/admin/treasury/'),

  /** Admin: Get all users */
  getUsers: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.get<{ users: any[]; total: number }>('/p2p/admin/users/'),

  /** Admin: Elevate or revoke a user's admin status */
  setUserAdminStatus: (client: ReturnType<typeof createAuthenticatedClient>, did: string, isAdmin: boolean) =>
    client.post('/p2p/admin/users/', { did, is_network_admin: isAdmin }),

  /** Admin: Manage user quota */
  getUserQuota: (client: ReturnType<typeof createAuthenticatedClient>, did: string) =>
    client.get<any>(`/p2p/admin/quota/${did}/`),

  /** Admin: Update user quota */
  updateUserQuota: (client: ReturnType<typeof createAuthenticatedClient>, did: string, quotaBytes: number) =>
    client.post(`/p2p/admin/quota/${did}/`, { quota_bytes: quotaBytes }),

  /** Miner: Trigger payout of all node earnings */
  payout: (client: ReturnType<typeof createAuthenticatedClient>) =>
    client.post('/storage/miner/payout/'),

  /** Admin: Get real system logs */
  getSystemLogs: (client: ReturnType<typeof createAuthenticatedClient>, lines: number = 100) =>
    client.get<{ logs: string[]; count: number }>(`/p2p/admin/logs/system/?lines=${lines}`),

  /** Miner/Admin: Get real-time logs for a specific node */
  getNodeLogs: (client: ReturnType<typeof createAuthenticatedClient>, nodeId: string, lines: number = 100) =>
    client.get<{ logs: string[]; count: number; node_id: string }>(`/storage/miner/logs/${nodeId}/?lines=${lines}`),
};
