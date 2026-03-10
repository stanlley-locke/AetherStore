import React, { useState, useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { createAuthenticatedClient, storageApi } from '../services/api';
import type { AetherObject } from '../services/api';
import { Globe, Plus, ExternalLink, Zap, CheckCircle, Search, Rocket } from 'lucide-react';
import './Drive.css'; // Reusing layout styles

interface NameRecord {
  name: string;
  target_object_id: string;
  owner_did: string;
  updated_at: string;
}

export const IpnsSites: React.FC = () => {
  const { did } = useAuthStore();
  const client = createAuthenticatedClient(did!);

  const [sites, setSites] = useState<NameRecord[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Publish form
  const [isPublishing, setIsPublishing] = useState(false);
  const [siteName, setSiteName] = useState('');
  const [targetId, setTargetId] = useState('');
  
  // Object search modal
  const [showSearch, setShowSearch] = useState(false);
  const [objects, setObjects] = useState<AetherObject[]>([]);
  
  const loadSites = async () => {
    setLoading(true);
    try {
      const res = await storageApi.listNames(client);
      setSites(res.data || []);
    } catch (e) {
      console.error('Failed to load sites:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadObjects = async () => {
    try {
      const res = await storageApi.listObjects(client, { page: 1, page_size: 50 });
      setObjects(res.data.objects || []);
    } catch (e) {
      console.error('Failed to load objects for search:', e);
    }
  };

  useEffect(() => { loadSites(); }, [did]);

  const handlePublish = async () => {
    if (!siteName || !targetId) return;
    try {
      await storageApi.publishName(client, siteName, targetId);
      setIsPublishing(false);
      setSiteName('');
      setTargetId('');
      loadSites();
    } catch (e: any) {
      alert(e.response?.data?.error || 'Publishing failed.');
    }
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString() + ' ' + new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="drive-container" style={{ flexDirection: 'column' }}>
      <div className="drive-action-bar">
        <h2 className="drive-title">IPNS Public Sites</h2>
        <button className="drive-btn-primary" onClick={() => { setIsPublishing(true); loadObjects(); }}>
          <Plus size={16} /> Publish New Site
        </button>
      </div>

      <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
        <Globe size={24} color="var(--accent)" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <p style={{ margin: '0 0 0.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Decentralized Web Hosting</p>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Publish any static HTML bundle or file from your AetherDrive to an <strong>IPNS NameRecord</strong>. Your site receives a permanent human-readable name and is accessible via any public DHT gateway — fully censorship-resistant.
          </p>
        </div>
      </div>

      {isPublishing && (
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', border: '1px solid var(--accent)' }}>
          <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Publish New NameRecord</h3>
          
          <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '-0.5rem' }}>IPNS Key Name (e.g., my-portfolio)</label>
          <input
            type="text"
            className="wallet-input"
            placeholder="Unique alias for the site..."
            value={siteName}
            onChange={e => setSiteName(e.target.value)}
            style={{ padding: '0.75rem 1rem', border: '1px solid var(--border-color)', borderRadius: '8px', background: 'var(--bg-panel)', color: 'var(--text-primary)', outline: 'none' }}
          />

          <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '-0.5rem' }}>Target Object ID</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              readOnly
              className="wallet-input"
              placeholder="Select an object to publish..."
              value={targetId}
              onClick={() => setShowSearch(true)}
              style={{ flex: 1, padding: '0.75rem 1rem', border: '1px solid var(--border-color)', borderRadius: '8px', background: 'var(--bg-panel)', color: 'var(--accent)', cursor: 'pointer', outline: 'none' }}
            />
            <button className="drive-btn-secondary" onClick={() => setShowSearch(true)}><Search size={18} /></button>
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
            <button className="drive-btn-primary" onClick={handlePublish} disabled={!siteName || !targetId} style={{ flex: 1, justifyContent: 'center' }}>
              <Zap size={16} /> Broadcast to DHT
            </button>
            <button className="drive-btn-secondary" onClick={() => setIsPublishing(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Target Object Search Modal */}
      {showSearch && (
        <div className="preview-overlay" onClick={() => setShowSearch(false)}>
          <div className="glass-panel" style={{ width: 500, padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: 0 }}>Select Target Object</h3>
            <div style={{ maxHeight: 300, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {objects.map(obj => (
                <div key={obj.id} onClick={() => { setTargetId(obj.id); setShowSearch(false); }} className="nav-item" style={{ cursor: 'pointer', background: 'var(--bg-hover)', border: '1px solid transparent' }}>
                  <Rocket size={16} />
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: 600 }}>{obj.filename || obj.id}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{obj.mime_type || 'Unknown type'} • {obj.id.slice(0, 16)}...</span>
                  </div>
                </div>
              ))}
              {objects.length === 0 && <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', textAlign: 'center' }}>No objects available in your Drive.</p>}
            </div>
            <button className="drive-btn-secondary" onClick={() => setShowSearch(false)} style={{ justifyContent: 'center' }}>Close</button>
          </div>
        </div>
      )}

      {/* Live Sites */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {loading ? (
          <div className="drive-loading"><div className="spinner" /><p>Finding DHT records...</p></div>
        ) : sites.length === 0 ? (
          <div className="drive-empty">
            <Globe size={48} color="var(--border-color)" />
            <h3>No NameRecords published</h3>
            <p>Publish an HTML file or ZIP to create a censorship-resistant website.</p>
          </div>
        ) : (
          sites.map(site => (
            <div key={site.name} className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <Globe size={24} color="var(--accent)" />
                <div>
                  <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-primary)', fontSize: '1.1rem' }}>{site.name}</p>
                  <code style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>→ {site.target_object_id}</code>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}>
                  <CheckCircle size={14} color="#10b981" />
                  <span style={{ color: '#10b981', fontWeight: 600 }}>Propagated</span>
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Updated {formatDate(site.updated_at)}</span>
                <a href={`http://localhost:8000/api/v1/storage/resolve/${site.name}/`} target="_blank" rel="noopener noreferrer" className="drive-btn-secondary" style={{ textDecoration: 'none' }}>
                  <ExternalLink size={14} /> Visit IPNS
                </a>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
