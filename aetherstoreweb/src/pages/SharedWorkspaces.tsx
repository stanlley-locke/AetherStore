import React, { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { createAuthenticatedClient, storageApi } from '../services/api';
import type { AetherObject } from '../services/api';
import { Link, Globe, Copy, CheckCircle, FileText, Activity } from 'lucide-react';
import './Drive.css'; // Reusing Layout CSS

export const SharedWorkspaces: React.FC = () => {
  const { did } = useAuthStore();
  const client = createAuthenticatedClient(did!);

  const [objects, setObjects] = useState<AetherObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [links, setLinks] = useState<Record<string, string>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expirySelection, setExpirySelection] = useState<Record<string, number>>({});

  const loadObjects = useCallback(async () => {
    setLoading(true);
    try {
      const res = await storageApi.listObjects(client, { page: 1, page_size: 100 });
      setObjects(res.data.objects || []);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [did]);

  useEffect(() => { loadObjects(); }, [loadObjects]);

  const generateLink = async (obj: AetherObject) => {
    try {
      const ttl = expirySelection[obj.id] || 604800; // Default 7 days
      const res = await storageApi.generatePresignedUrl(client, obj.id, ttl); 
      // The backend returns a url like /api/v1/download/presigned/<token>/
      // We want to extract the token and create a frontend link
      const tokenMatch = res.data.url.match(/presigned\/([^/]+)\/?/);
      const token = tokenMatch ? tokenMatch[1] : '';
      
      const origin = window.location.origin;
      const fullUrl = `${origin}/share/${token}`;
      setLinks(prev => ({ ...prev, [obj.id]: fullUrl }));
    } catch (e: any) {
      alert(e.response?.data?.error || 'Failed to generate link.');
    }
  };

  const handleExpiryChange = (id: string, value: number) => {
    setExpirySelection(prev => ({ ...prev, [id]: value }));
  };

  const copyLink = (id: string, url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="drive-container">
      <div className="drive-action-bar" style={{ alignItems: 'center' }}>
        <h2 className="drive-title">Public Links</h2>
        <div className="drive-actions">
          <button className="drive-btn-secondary" onClick={loadObjects} disabled={loading} title="Refresh Files">
            <Activity size={16} className={loading ? "spinner-icon" : ""} /> Refresh
          </button>
        </div>
      </div>

      <div className="file-panel">
        {loading ? (
          <div className="drive-empty">
            <Activity size={32} className="spinner-icon" />
            <p>Loading files...</p>
          </div>
        ) : objects.length === 0 ? (
          <div className="drive-empty">
            <Globe size={48} color="var(--accent)" />
            <p>No files found. Upload files in My Drive to share them.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="file-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th style={{ width: '45%' }}>Public Link</th>
                  <th className="actions-col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {objects.map(obj => (
                  <tr key={obj.id} className="file-row">
                    <td className="file-name-cell">
                      <FileText size={18} className="file-icon" />
                      <div className="file-name-wrapper">
                        <span className="file-name" title={obj.filename}>{obj.filename || obj.id}</span>
                      </div>
                    </td>
                    <td className="file-meta" style={{ width: '50%' }}>
                      {links[obj.id] ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-hover)', padding: '0.5rem', borderRadius: '8px', overflow: 'hidden' }}>
                          <span style={{ fontSize: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--accent)' }}>
                            {links[obj.id]}
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Not shared publicly</span>
                      )}
                    </td>
                    <td className="file-actions">
                      {links[obj.id] ? (
                        <button className="action-icon-btn" title="Copy Link" onClick={() => copyLink(obj.id, links[obj.id])}>
                          {copiedId === obj.id ? <CheckCircle size={15} color="#10b981" /> : <Copy size={15} />}
                        </button>
                      ) : (
                        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                          <select 
                            className="drive-btn-secondary" 
                            style={{ padding: '0.3rem', fontSize: '0.75rem', height: 'auto', minWidth: 'auto' }}
                            value={expirySelection[obj.id] || 604800}
                            onChange={(e) => handleExpiryChange(obj.id, parseInt(e.target.value))}
                          >
                            <option value={3600}>1 Hour</option>
                            <option value={86400}>24 Hours</option>
                            <option value={604800}>7 Days</option>
                          </select>
                          <button className="drive-btn-secondary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }} onClick={() => generateLink(obj)}>
                            <Link size={14} /> Generate Link
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
