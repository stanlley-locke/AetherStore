import React, { useState, useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { createAuthenticatedClient, storageApi } from '../services/api';
import type { AetherObject } from '../services/api';
import { Trash2, AlertTriangle, RefreshCw, FileText } from 'lucide-react';
import './Drive.css'; // Reusing layout classes

export const Trash: React.FC = () => {
  const { did } = useAuthStore();
  const client = createAuthenticatedClient(did!);

  const [objects, setObjects] = useState<AetherObject[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTrash = async () => {
    setLoading(true);
    try {
      const res = await storageApi.listTrash(client);
      setObjects(res.data.objects || []);
    } catch (e: any) {
      console.error('Failed to load trash:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTrash(); }, [did]);

  const handleRestore = async (obj: AetherObject) => {
    try {
      await storageApi.restoreObject(client, obj.id);
      setObjects(prev => prev.filter(o => o.id !== obj.id));
    } catch (e: any) {
      alert(e.response?.data?.error || 'Restore failed.');
    }
  };

  const formatSize = (bytes: number | null) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const formatDate = (iso: string) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString();
  };

  return (
    <div className="drive-container" style={{ flexDirection: 'column' }}>
      <div className="drive-action-bar">
        <h2 className="drive-title">Recycle Bin</h2>
      </div>

      <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--bg-hover)', borderColor: 'var(--border-color)' }}>
        <AlertTriangle size={18} color="#f59e0b" />
        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Files in the Recycle Bin will be swept by the <strong>Kademlia Garbage Collector</strong> and permanently shredded from the DHT within 30 days.
        </p>
      </div>

      <div className="file-panel">
        {loading ? (
          <div className="drive-loading">
            <div className="spinner" />
            <p>Loading recycle bin...</p>
          </div>
        ) : objects.length === 0 ? (
          <div className="drive-empty">
            <Trash2 size={52} />
            <h3>Recycle Bin is empty</h3>
            <p>No soft-deleted files found.</p>
          </div>
        ) : (
          <table className="file-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Size</th>
                <th>Deleted On</th>
                <th>Status</th>
                <th className="actions-col" style={{ textAlign: 'right' }}>Restore</th>
              </tr>
            </thead>
            <tbody>
              {objects.map(obj => (
                <tr key={obj.id} className="file-row">
                  <td className="file-name-cell" style={{ opacity: 0.7 }}>
                    <FileText size={18} className="file-icon" />
                    <span className="file-name">{obj.filename || obj.id}</span>
                  </td>
                  <td className="file-meta">{formatSize(obj.size)}</td>
                  <td className="file-meta">{formatDate(obj.created_at)}</td>
                  <td>
                    <span className="encrypted-badge" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>Pending GC</span>
                  </td>
                  <td className="file-actions" style={{ justifyContent: 'flex-end' }}>
                    <button className="drive-btn-secondary" title="Restore" onClick={() => handleRestore(obj)}>
                      <RefreshCw size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
