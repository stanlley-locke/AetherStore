import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { KeyRound, ShieldAlert, ArrowRight, UploadCloud, Copy, Check } from 'lucide-react';
import axios from 'axios';
import logo from '../assets/cloud-computing.png';
import './Login.css';

const API_BASE_URL = '/api/v1';

export const Login: React.FC = () => {
  const { login } = useAuthStore();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'create' | 'recover'>('create');
  
  const [mnemonicInput, setMnemonicInput] = useState('');
  const [copied, setCopied] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New Wallet State
  const [newWallet, setNewWallet] = useState<{
    mnemonic: string;
    address: string;
    did: string;
    publicKey: string;
    privateKey: string;
  } | null>(null);

  const handleGenerateWallet = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // In a fully pure dApp, we generate bip-39 mnemonics locally in standard JS.
      // For this prototype, we'll ask the backend to generate the keys securely, but it drops the mnemonic immediately.
      // We use the new fully unauthenticated endpoint directly
      const response = await axios.post(`${API_BASE_URL}/billing/wallet/generate/`);
      const data = response.data;
      setNewWallet({
        mnemonic: data.mnemonic,
        address: data.address,
        did: data.did,
        publicKey: data.public_key || data.publicKey,
        privateKey: data.private_key || data.privateKey
      });
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to generate Web3 wallet');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRecoverWallet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mnemonicInput.trim() || mnemonicInput.trim().split(' ').length !== 12) {
      setError('Please enter a valid 12-word recovery phrase.');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/billing/wallet/recover/`, {
        mnemonic: mnemonicInput.trim()
      });
      
      const { address, did, public_key, private_key } = response.data;
      login(mnemonicInput.trim(), address, public_key, private_key, did);
      navigate('/drive');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to recover wallet. Invalid mnemonic.');
    } finally {
      setIsLoading(false);
    }
  };

  const completeOnboarding = () => {
    if (newWallet) {
      login(newWallet.mnemonic, newWallet.address, newWallet.publicKey, newWallet.privateKey, newWallet.did);
      navigate('/drive');
    }
  };

  const handleCopy = async () => {
    if (newWallet) {
      await navigator.clipboard.writeText(newWallet.mnemonic);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card glass-panel">
        
        <div className="login-header">
          <img src={logo} alt="AetherStore Logo" className="login-logo" />
          <h1>AetherStore</h1>
          <p>Decentralized Identity & Storage</p>
        </div>

        {!newWallet ? (
          <>
            <div className="tabs">
              <button 
                className={`tab ${activeTab === 'create' ? 'active' : ''}`}
                onClick={() => { setActiveTab('create'); setError(null); }}
              >
                Create Wallet
              </button>
              <button 
                className={`tab ${activeTab === 'recover' ? 'active' : ''}`}
                onClick={() => { setActiveTab('recover'); setError(null); }}
              >
                Recover Wallet
              </button>
            </div>

            {error && <div className="error-banner">{error}</div>}

            {activeTab === 'create' ? (
              <div className="tab-content">
                <p className="description-text">
                  Generate a non-custodial Web3 wallet. AetherStore uses a 12-word mnemonic phrase to establish your permanent <strong>Zero-Knowledge Identity (DID)</strong>. No emails or passwords required.
                </p>
                <button 
                  className="primary-button" 
                  onClick={handleGenerateWallet}
                  disabled={isLoading}
                >
                  {isLoading ? 'Generating Keys...' : 'Generate New Secure Wallet'}
                  <KeyRound size={18} />
                </button>
              </div>
            ) : (
              <div className="tab-content">
                <form onSubmit={handleRecoverWallet}>
                  <p className="description-text">
                    Paste your 12-word mnemonic sequence below to instantly restore access to your encrypted drives, chat history, and ATK coin balance.
                  </p>
                  <textarea 
                    className="mnemonic-input"
                    placeholder="word1 word2 word3..."
                    value={mnemonicInput}
                    onChange={(e) => setMnemonicInput(e.target.value)}
                    rows={3}
                  />
                  <button 
                    type="submit" 
                    className="primary-button outline" 
                    disabled={isLoading}
                  >
                    {isLoading ? 'Decrypting...' : 'Recover Account'}
                    <UploadCloud size={18} />
                  </button>
                </form>
              </div>
            )}
          </>
        ) : (
          <div className="success-content">
            <div className="warning-banner">
              <ShieldAlert size={24} color="#f59e0b" style={{ flexShrink: 0 }} />
              <div>
                <strong>CRITICAL: Save your Secret Phrase!</strong>
                <p>This 12-word phrase is the ONLY way to recover your account and decrypted files. AetherStore cannot reset it if lost.</p>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong style={{ fontSize: '0.875rem' }}>Your Recovery Phrase</strong>
              <button 
                onClick={handleCopy}
                style={{ 
                  background: 'none', border: 'none', color: 'var(--accent-primary)', 
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', fontWeight: 600
                }}
              >
                {copied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy to clipboard</>}
              </button>
            </div>

            <div className="phrase-box font-mono">
              {newWallet.mnemonic.split(' ').map((word, i) => (
                <div key={i} className="word-chip">
                  <span className="word-index">{i + 1}</span>
                  {word}
                </div>
              ))}
            </div>

            <div className="address-display">
              <label>Public Wallet Address:</label>
              <div className="font-mono hash-text">{newWallet.address}</div>
            </div>

            <button className="primary-button" onClick={completeOnboarding}>
              I have saved my phrase securely <ArrowRight size={18} />
            </button>
          </div>
        )}

      </div>
    </div>
  );
};
