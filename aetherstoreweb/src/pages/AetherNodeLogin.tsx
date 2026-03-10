import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { KeyRound, ArrowLeft } from 'lucide-react';
import axios from 'axios';
import logo from '../assets/cloud-computing.png';
import './Login.css';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export const AetherNodeLogin: React.FC = () => {
  const { login } = useAuthStore();
  const navigate = useNavigate();
  const [mnemonicInput, setMnemonicInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRecoverWallet = async (e: React.FormEvent) => {
    e.preventDefault();
    const words = mnemonicInput.trim().split(/\s+/);
    if (words.length < 12) {
      setError('Please enter a valid 12-word or longer recovery phrase.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // 1. Recover the wallet
      const recoverRes = await axios.post(`${API_BASE_URL}/billing/wallet/recover/`, {
        mnemonic: mnemonicInput.trim()
      });
      const { address, did, public_key, private_key } = recoverRes.data;

      // 2. Log in so we have auth credentials
      login(mnemonicInput.trim(), address, public_key, private_key, did);

      // 3. Verify this wallet has network admin privileges
      const ts = Math.floor(Date.now() / 1000);
      const nonce = `${did.replace(/[^a-z0-9]/gi, '')}${ts}${Math.random().toString(36).slice(2)}`;
      const authHeader = `DID-Signature ${did}:fakesig:${ts}:${nonce}`;

      const adminRes = await axios.get(`${API_BASE_URL}/p2p/admin/status/`, {
        headers: { Authorization: authHeader }
      });

      if (!adminRes.data.is_network_admin) {
        // Not an admin — log them out and show error
        useAuthStore.getState().logout();
        setError('This wallet does not have AetherNode administrator privileges. Please use your admin wallet, or contact the network creator.');
        setIsLoading(false);
        return;
      }

      // 4. Redirect to admin portal
      navigate('/aethernode');
    } catch (err: any) {
      useAuthStore.getState().logout();
      setError(err.response?.data?.error || 'Failed to authenticate. Check your recovery phrase.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card" style={{ maxWidth: '460px' }}>

        <div className="login-header">
          <img src={logo} alt="AetherNode" className="login-logo" />
          <h1>AetherNode</h1>
          <p>Network Operations Console</p>
        </div>

        <div style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          padding: '0.875rem 1rem',
          marginBottom: '1.5rem',
          fontSize: '0.85rem',
          color: 'var(--text-muted)',
          lineHeight: 1.5
        }}>
          <strong style={{ color: 'var(--text-primary)' }}>Admin Access Required.</strong>{' '}
          Enter the 12-word recovery phrase of your designated network admin wallet. Non-admin wallets will be denied.
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleRecoverWallet}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Admin Wallet Recovery Phrase
          </label>
          <textarea
            className="mnemonic-input"
            placeholder="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
            value={mnemonicInput}
            onChange={(e) => setMnemonicInput(e.target.value)}
            rows={3}
            style={{ resize: 'none' }}
          />
          <button
            type="submit"
            className="primary-button"
            disabled={isLoading}
            style={{ marginTop: '1rem' }}
          >
            {isLoading ? 'Authenticating...' : 'Access Admin Console'}
            <KeyRound size={18} />
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
          <button
            onClick={() => navigate('/login')}
            style={{
              background: 'none', border: 'none', color: 'var(--text-muted)',
              cursor: 'pointer', display: 'inline-flex', alignItems: 'center',
              gap: '0.375rem', fontSize: '0.85rem', fontWeight: 500
            }}
          >
            <ArrowLeft size={14} />
            Back to AetherStore
          </button>
        </div>

      </div>
    </div>
  );
};
