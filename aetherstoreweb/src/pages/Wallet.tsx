import React, { useState, useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { createAuthenticatedClient, walletApi } from '../services/api';
import type { WalletBalance } from '../services/api';
import { ArrowDownLeft, ArrowUpRight, RefreshCw, Send, Copy, Check, AlertCircle } from 'lucide-react';
import nacl from 'tweetnacl';
import './Wallet.css';

export const Wallet: React.FC = () => {
  const { did, walletAddress, privateKey, publicKey } = useAuthStore();
  const client = React.useMemo(() => {
    return did ? createAuthenticatedClient(did) : null;
  }, [did]);

  const [walletData, setWalletData] = useState<WalletBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'send' | 'receive' | 'deposit'>('send');
  const [recipient, setRecipient] = useState('');
  const [amount, setAmount] = useState('');
  const [depositAmount, setDepositAmount] = useState('');
  const [txLoading, setTxLoading] = useState(false);
  const [txSuccess, setTxSuccess] = useState<string | null>(null);
  const [txError, setTxError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const loadWallet = React.useCallback(async () => {
    if (!client) return;
    setLoading(true);
    setError(null);
    try {
      const res = await walletApi.getBalance(client);
      setWalletData(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to load wallet. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => { 
    if (did && client) {
      loadWallet(); 
    }
  }, [did, client, loadWallet]);


  const copyAddress = () => {
    navigator.clipboard.writeText(walletAddress || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDeposit = async () => {
    if (!client || !depositAmount || isNaN(parseFloat(depositAmount))) return;
    setTxLoading(true); setTxError(null); setTxSuccess(null);
    try {
      await client.post('/billing/deposit/', { amount: depositAmount });
      setTxSuccess(`Successfully deposited ${depositAmount} ATK`);
      setDepositAmount('');
      await loadWallet();
    } catch (e: any) {
      setTxError(e.response?.data?.error || 'Deposit failed.');
    } finally {
      setTxLoading(false);
    }
  };

  const handleTransfer = async () => {
    if (!client || !recipient.trim() || !amount || isNaN(parseFloat(amount))) return;
    if (!privateKey || !publicKey) {
      setTxError('Session keys not found. Please re-login to load your Ed25519 keypair.');
      return;
    }
    setTxLoading(true); setTxError(null); setTxSuccess(null);
    try {
      const cleanRecipient = recipient.trim().toLowerCase();
      const timestamp = Math.floor(Date.now() / 1000).toString();
      const message = `${cleanRecipient}:${amount}:${timestamp}`;
      
      // Real Ed25519 signing
      const privBytes = new Uint8Array(privateKey!.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16)));
      const msgBytes = new TextEncoder().encode(message);
      // nacl.sign.detached requires a 64-byte secretKey (seed + publicKey)
      const keyPair = nacl.sign.keyPair.fromSeed(privBytes);
      const signatureBytes = nacl.sign.detached(msgBytes, keyPair.secretKey);
      const signature = Array.from(signatureBytes).map(b => b.toString(16).padStart(2, '0')).join('');

      await walletApi.transfer(client, {
        public_key: publicKey!,
        recipient_address: cleanRecipient,
        amount,
        timestamp,
        signature,
      });
      setTxSuccess(`Sent ${amount} ATK to ${recipient.slice(0, 14)}...`);
      setRecipient(''); setAmount('');
      await loadWallet();
    } catch (e: any) {
      setTxError(e.response?.data?.error || 'Transfer failed. Ensure both wallets exist on the network.');
    } finally {
      setTxLoading(false);
    }
  };

  const balance = walletData?.balance ?? 0;
  const transactions = walletData?.recent_transactions ?? [];

  if (loading) {
    return (
      <div className="wallet-loading">
        <div className="spinner" />
        <p>Fetching wallet data from the ledger...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wallet-error">
        <AlertCircle size={32} />
        <p>{error}</p>
        <button className="drive-btn-primary" onClick={loadWallet}>Retry</button>
      </div>
    );
  }

  return (
    <div className="wallet-container">
      <div className="wallet-main">
        {/* ── Balance Hero ── */}
        <div className="balance-card">
          <div className="balance-info">
            <p className="balance-label">Total Portfolio Balance</p>
            <h1 className="balance-amount">
              {balance.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 })}
              <span className="balance-unit">ATK</span>
            </h1>
            <div className="balance-address-row">
              <span className="balance-did">{did}</span>
              <button className="copy-btn-mini" onClick={copyAddress} title="Copy Address">
                {copied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
              </button>
            </div>
          </div>
          <div className="balance-quick-actions">
            <button className="balance-pill primary" onClick={() => setActiveTab('send')}>
              <Send size={15} /> Send
            </button>
            <button className="balance-pill" onClick={() => setActiveTab('deposit')}>
              <ArrowDownLeft size={15} /> Receive
            </button>
            <button className="balance-pill refresh" onClick={loadWallet}>
              <RefreshCw size={15} />
            </button>
          </div>
        </div>

        {/* ── Action Center ── */}
        <div className="action-center-grid">
          <div className="sr-card">
            <div className="sr-tab-bar">
              <button className={`sr-tab ${activeTab === 'send' ? 'active' : ''}`} onClick={() => setActiveTab('send')}>
                <Send size={14} /> Send ATK
              </button>
              <button className={`sr-tab ${activeTab === 'receive' ? 'active' : ''}`} onClick={() => setActiveTab('receive')}>
                <ArrowDownLeft size={14} /> My Address
              </button>
              <button className={`sr-tab ${activeTab === 'deposit' ? 'active' : ''}`} onClick={() => setActiveTab('deposit')}>
                <ArrowUpRight size={14} /> Deposit
              </button>
            </div>

            {/* Feedback Banner */}
            {txSuccess && <div className="tx-banner success"><Check size={14} /> {txSuccess}</div>}
            {txError && <div className="tx-banner error"><AlertCircle size={14} /> {txError}</div>}

            <div className="sr-body">
              {activeTab === 'send' && (
                <>
                  <div className="field-group">
                    <label>Recipient Address</label>
                    <input 
                      className="wallet-field" 
                      type="text" 
                      placeholder="ath1... or did:aether:ath1..." 
                      value={recipient} 
                      onChange={e => setRecipient(e.target.value)} 
                    />
                  </div>
                  <div className="field-group">
                    <label>Amount (ATK)</label>
                    <input 
                      className="wallet-field" 
                      type="number" 
                      placeholder="0.0000" 
                      value={amount} 
                      onChange={e => setAmount(e.target.value)} 
                    />
                  </div>
                  <p className="field-hint">
                    <AlertCircle size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                    Network fee: 0.001 ATK · Signed locally with Ed25519
                  </p>
                  <button className="drive-btn-primary w-full" onClick={handleTransfer} disabled={txLoading || !amount || !recipient}>
                    {txLoading ? 'Broadcasting...' : <><Send size={15} /> Sign & Send Transaction</>}
                  </button>
                </>
              )}
              {activeTab === 'receive' && (
                <>
                  <label>Your Public Wallet Address</label>
                  <div className="address-box-large">
                    <div className="qr-placeholder">
                      {/* In a real app, a QR code would go here */}
                      <div className="qr-inner">
                        <ArrowDownLeft size={48} opacity={0.1} />
                      </div>
                    </div>
                    <code className="full-address">{walletAddress}</code>
                    <button className="drive-btn-secondary" onClick={copyAddress} style={{ marginTop: '1rem' }}>
                      {copied ? <><Check size={15} /> Copied</> : <><Copy size={15} /> Copy to Clipboard</>}
                    </button>
                  </div>
                  <p className="field-hint center">Only send ATK tokens to this address on the AetherStore network.</p>
                </>
              )}
              {activeTab === 'deposit' && (
                <>
                  <div className="field-group">
                    <label>Deposit Amount (ATK)</label>
                    <input 
                      className="wallet-field" 
                      type="number" 
                      placeholder="500.00" 
                      value={depositAmount} 
                      onChange={e => setDepositAmount(e.target.value)} 
                    />
                  </div>
                  <p className="field-hint">Testnet Mode: Simulates a top-up from a payment provider for development purposes.</p>
                  <button className="drive-btn-primary w-full" onClick={handleDeposit} disabled={txLoading || !depositAmount}>
                    {txLoading ? 'Processing...' : <><ArrowDownLeft size={15} /> Deposit Funds</>}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* ── Ledger History ── */}
          <div className="ledger-card">
            <div className="ledger-header">
              <h3>Recent Activity</h3>
              <button className="view-all-btn" onClick={loadWallet}>Refresh</button>
            </div>
            {transactions.length === 0 ? (
              <div className="ledger-empty-state">
                <RefreshCw size={32} opacity={0.2} />
                <p>No transactions found in this wallet's history.</p>
              </div>
            ) : (
              <div className="ledger-list">
                {transactions.map(tx => (
                  <div key={tx.id} className="ledger-item">
                    <div className={`tx-icon-wrap ${tx.amount > 0 ? 'in' : 'out'}`}>
                      {tx.amount > 0 ? <ArrowDownLeft size={16} /> : <ArrowUpRight size={16} />}
                    </div>
                    <div className="tx-details">
                      <p className="tx-desc">{tx.description}</p>
                      <p className="tx-date">{tx.date ? new Date(tx.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'Pending'}</p>
                    </div>
                    <div className={`tx-value ${tx.amount > 0 ? 'pos' : 'neg'}`}>
                      {tx.amount > 0 ? '+' : ''}{tx.amount.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
