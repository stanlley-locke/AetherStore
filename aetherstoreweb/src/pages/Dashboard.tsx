import React from 'react';
import { Database, Server, Key, Shield } from 'lucide-react';
import { useAuthStore } from '../store/useAuthStore';
import logo from '../assets/cloud-computing.png';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  const { did, walletAddress } = useAuthStore();
  return (
    <div className="dashboard">
      <div className="dashboard-header-brand">
        <img src={logo} alt="AetherStore Logo" className="dashboard-logo" />
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Welcome to AetherStore</h1>
      </div>
      
      <div className="stats-grid">
        <div className="stat-card glass-panel">
          <div className="stat-header">
            <h3>Used Capacity</h3>
            <Database size={20} color="var(--accent-primary)" />
          </div>
          <div className="stat-value font-mono">15.4 GB</div>
          <p className="stat-subtext">of 50 GB Quota</p>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-header">
            <h3>ATK Balance</h3>
            <Shield size={20} color="var(--accent-primary)" />
          </div>
          <div className="stat-value font-mono">24,500.00</div>
          <p className="stat-subtext">Estimated: $1,200 USD</p>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-header">
            <h3>Active Shards</h3>
            <Server size={20} color="var(--accent-primary)" />
          </div>
          <div className="stat-value font-mono">2,104</div>
          <p className="stat-subtext">Over 14 nodes</p>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-header">
            <h3>Identity (DID)</h3>
            <Key size={20} color="var(--accent-primary)" />
          </div>
          <div className="stat-value hash-text" style={{ fontSize: '0.8rem' }}>{did || 'Not Authenticated'}</div>
          <p className="stat-subtext" style={{ fontSize: '0.7rem' }}>Wallet: {walletAddress}</p>
        </div>
      </div>
      
      <div style={{ marginTop: '3rem' }}>
        <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem' }}>Recent Activity</h2>
        <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No recent activity to display.
        </div>
      </div>
    </div>
  );
};
