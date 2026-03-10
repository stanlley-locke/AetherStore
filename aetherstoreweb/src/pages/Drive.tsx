import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { createAuthenticatedClient, storageApi } from '../services/api';
import type { AetherObject } from '../services/api';
import {
  FileText, UploadCloud, Plus, ShieldCheck, Activity, Database,
  Trash2, X, CheckCircle, Clock, AlertCircle, RefreshCw, Download, Play, Grid, List
} from 'lucide-react';
import './Drive.css';

interface UploadJob {
  id: string;
  file: File;
  progress: number;
  status: 'uploading' | 'done' | 'error';
  error?: string;
}

const BUCKETS = ['personal', 'media', 'documents', 'backups'];

export const Drive: React.FC = () => {
  const { did, walletAddress } = useAuthStore();
  
  // Memoize client to avoid recreation, but only if did is present
  const client = React.useMemo(() => did ? createAuthenticatedClient(did) : null, [did]);

  const [objects, setObjects] = useState<AetherObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedBucket, setSelectedBucket] = useState('personal');
  const [uploadJobs, setUploadJobs] = useState<UploadJob[]>([]);
  const [showUploadWidget, setShowUploadWidget] = useState(false);
  const [previewObj, setPreviewObj] = useState<AetherObject | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadObjects = useCallback(async () => {
    if (!client) return;
    setLoading(true);
    setError(null);
    try {
      const res = await storageApi.listObjects(client, { page: 1, page_size: 100 });
      setObjects(res.data.objects || []);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to load files. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => { 
    if (client) loadObjects(); 
  }, [client, loadObjects]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setShowUploadWidget(true);
    files.forEach(file => startUpload(file));
    e.target.value = '';
  };

  const startUpload = (file: File) => {
    if (!client) return;
    const jobId = `${Date.now()}-${file.name}`;
    setUploadJobs(prev => [...prev, { id: jobId, file, progress: 0, status: 'uploading' }]);

    storageApi.upload(client, selectedBucket, file, (progress) => {
      setUploadJobs(prev =>
        prev.map(j => j.id === jobId ? { ...j, progress } : j)
      );
    })
    .then(() => {
      setUploadJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'done', progress: 100 } : j));
      setTimeout(() => loadObjects(), 2000); // Wait for Celery
    })
    .catch((err) => {
      setUploadJobs(prev =>
        prev.map(j => j.id === jobId ? { ...j, status: 'error', error: err.response?.data?.error || 'Upload failed' } : j)
      );
    });
  };

  const handleDelete = async (obj: AetherObject) => {
    if (!client || !confirm(`Move "${obj.filename || 'Unknown File'}" to Recycle Bin?`)) return;
    try {
      await storageApi.deleteObject(client, obj.id);
      setObjects(prev => prev.filter(o => o.id !== obj.id));
    } catch (e: any) {
      alert(e.response?.data?.error || 'Delete failed.');
    }
  };

  const handleDownload = async (obj: AetherObject) => {
    if (!client) return;
    try {
      await storageApi.startDownload(client, obj.id);
      alert(`Download queued for "${obj.filename || 'Unknown File'}". Check the Celery worker status.`);
    } catch (e: any) {
      alert(e.response?.data?.error || 'Download request failed.');
    }
  };

  const formatSize = (bytes: number | null) => {
    if (!bytes && bytes !== 0) return '—';
    if (bytes === 0) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const formatDate = (iso: string) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const isMedia = (obj: AetherObject) =>
    (obj.mime_type || '').startsWith('video/') || (obj.mime_type || '').startsWith('audio/');

  // Dashboard Stats Calculations
  const totalBytes = objects.reduce((sum, o) => sum + (o.size || 0), 0);
  const quotaBytes = 100 * 1024 * 1024 * 1024; // 100 GB
  const usagePercent = totalBytes > 0 ? Math.max((totalBytes / quotaBytes) * 100, 0.1).toFixed(2) : '0.00';
  
  // Daily Burn ATK (0.001 per GB per day)
  const burnRaw = (totalBytes / 1e9) * 0.001;
  const dailyBurnATK = burnRaw > 0 && burnRaw < 0.0001 ? '< 0.0001' : burnRaw.toFixed(4);

  return (
    <div className="drive-container">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileSelect}
      />

      {/* ── Top Dashboard KPIs ── */}
      <div className="kpi-grid">
        {/* Storage Quota Card */}
        <div className="kpi-card storage-card">
          <div className="kpi-header">
            <h3><Database size={16} /> Storage Quota</h3>
            <span className="kpi-badge">{usagePercent}% Used</span>
          </div>
          <div className="kpi-body">
            <h1 className="kpi-value">{formatSize(totalBytes)} <span className="kpi-unit">/ 100 GB</span></h1>
            <div className="kpi-progress-bg">
              <div className="kpi-progress-fill" style={{ width: `${Math.min(Number(usagePercent), 100)}%` }}></div>
            </div>
            <p className="kpi-hint">{objects.length} files stored safely across the Kademlia DHT</p>
          </div>
        </div>

        {/* Network Burn Card */}
        <div className="kpi-card network-card">
          <div className="kpi-header">
            <h3><Activity size={16} /> Network Rent (Daily)</h3>
            <span className="kpi-badge burn-badge">Auto-Pay</span>
          </div>
          <div className="kpi-body">
            <h1 className="kpi-value warning-text">–{dailyBurnATK} <span className="kpi-unit">ATK</span></h1>
            <div className="kpi-identities">
              <div className="identity-row">
                <span>DID:</span>
                <code>{did ? `${did.slice(0, 16)}...` : 'Unknown'}</code>
              </div>
              <div className="identity-row">
                <span>Wallet:</span>
                <code>{walletAddress ? `${walletAddress.slice(0, 12)}...` : 'Unknown'}</code>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Main Content Area ── */}
      <div className="drive-main">
        {/* Action Bar */}
        <div className="drive-action-bar">
          <div className="bucket-pills">
            {BUCKETS.map(b => (
              <button
                key={b}
                className={`bucket-pill ${selectedBucket === b ? 'active' : ''}`}
                onClick={() => setSelectedBucket(b)}
              >
                {b}
              </button>
            ))}
          </div>
          <div className="drive-actions">
            <div className="view-toggle">
              <button 
                className={`view-btn ${viewMode === 'list' ? 'active' : ''}`} 
                onClick={() => setViewMode('list')}
                title="List View"
              >
                <List size={16} />
              </button>
              <button 
                className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`} 
                onClick={() => setViewMode('grid')}
                title="Grid View"
              >
                <Grid size={16} />
              </button>
            </div>
            <button className="drive-btn-secondary" onClick={loadObjects} title="Refresh Files">
              <RefreshCw size={16} />
            </button>
            <button className="drive-btn-primary" onClick={() => fileInputRef.current?.click()}>
              <Plus size={18} /> Upload Files
            </button>
          </div>
        </div>

        {/* Status Panels */}
        {error && (
          <div className="drive-alert error">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button onClick={loadObjects} className="alert-retry">Retry</button>
          </div>
        )}

        {/* File Table */}
        <div className="file-panel">
          {loading ? (
            <div className="drive-loading">
              <div className="spinner" />
              <p>Fetching encrypted shards from the DHT...</p>
            </div>
          ) : objects.length === 0 ? (
            <div className="drive-empty" onClick={() => fileInputRef.current?.click()}>
              <UploadCloud size={52} />
              <h3>Your AetherDrive is empty</h3>
              <p>Click to upload — files are instantly sharded and encrypted before entering the network.</p>
            </div>
          ) : (
            <div className={`table-responsive ${viewMode === 'grid' ? 'grid-mode' : ''}`}>
              {viewMode === 'list' ? (
                <table className="file-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Size</th>
                      <th>Type</th>
                      <th>Uploaded</th>
                      <th className="actions-col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {objects.map(obj => (
                      <tr key={obj.id} className="file-row">
                        <td className="file-name-cell">
                          {isMedia(obj)
                            ? <Play size={18} className="file-icon media" />
                            : <FileText size={18} className="file-icon" />
                          }
                          <div className="file-name-wrapper">
                            <span className="file-name" title={obj.filename}>{obj.filename || obj.id}</span>
                            {obj.root_hash && (
                              <span className="encrypted-badge"><ShieldCheck size={11} /> Encrypted</span>
                            )}
                          </div>
                        </td>
                        <td className="file-meta">{formatSize(obj.size)}</td>
                        <td className="file-meta">{obj.mime_type || '—'}</td>
                        <td className="file-meta">{formatDate(obj.created_at)}</td>
                        <td className="file-actions">
                          {isMedia(obj) && (
                            <button className="action-icon-btn preview-btn" title="Stream" onClick={() => setPreviewObj(obj)}>
                              <Play size={15} />
                            </button>
                          )}
                          <button className="action-icon-btn" title="Download" onClick={() => handleDownload(obj)}>
                            <Download size={15} />
                          </button>
                          <button className="action-icon-btn danger-btn" title="Delete" onClick={() => handleDelete(obj)}>
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="file-grid">
                  {objects.map(obj => (
                    <div key={obj.id} className="grid-card">
                      <div className="grid-card-icon">
                        {isMedia(obj)
                          ? <Play size={32} className="file-icon media" />
                          : <FileText size={32} className="file-icon" />
                        }
                      </div>
                      <div className="grid-card-info">
                        <span className="grid-filename" title={obj.filename}>{obj.filename || obj.id}</span>
                        <span className="grid-meta">{formatSize(obj.size)} • {formatDate(obj.created_at)}</span>
                        {obj.root_hash && (
                          <span className="encrypted-badge"><ShieldCheck size={11} /> Encrypted</span>
                        )}
                      </div>
                      <div className="grid-card-actions">
                        {isMedia(obj) && (
                          <button className="action-icon-btn preview-btn" title="Stream" onClick={() => setPreviewObj(obj)}>
                            <Play size={15} />
                          </button>
                        )}
                        <button className="action-icon-btn" title="Download" onClick={() => handleDownload(obj)}>
                          <Download size={15} />
                        </button>
                        <button className="action-icon-btn danger-btn" title="Delete" onClick={() => handleDelete(obj)}>
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Upload Progress Widget ── */}
      {showUploadWidget && uploadJobs.length > 0 && (
        <div className="upload-widget">
          <div className="upload-widget-header">
            <span><UploadCloud size={16} /> {uploadJobs.filter(j => j.status === 'uploading').length} Uploading...</span>
            <button className="close-btn" onClick={() => setShowUploadWidget(false)}><X size={16} /></button>
          </div>
          {uploadJobs.slice(-5).map(job => (
            <div key={job.id} className="upload-item">
              <div className="upload-item-name">
                {job.status === 'done' && <CheckCircle size={14} color="#10b981" />}
                {job.status === 'error' && <AlertCircle size={14} color="#ef4444" />}
                {job.status === 'uploading' && <Clock size={14} color="var(--accent)" />}
                <span>{job.file.name}</span>
              </div>
              {job.status === 'uploading' && (
                <div className="upload-bar"><div className="upload-fill" style={{ width: `${job.progress}%` }} /></div>
              )}
              {job.status === 'error' && <span className="upload-error">{job.error}</span>}
            </div>
          ))}
        </div>
      )}

      {/* ── Media Preview Modal ── */}
      {previewObj && (
        <div className="preview-overlay" onClick={() => setPreviewObj(null)}>
          <div className="preview-modal" onClick={e => e.stopPropagation()}>
            <div className="preview-header">
              <span className="preview-title">{previewObj.filename || previewObj.id}</span>
              <button onClick={() => setPreviewObj(null)}><X size={20} /></button>
            </div>
            {(previewObj.mime_type || '').startsWith('video/') ? (
              <video
                controls
                autoPlay
                style={{ width: '100%', borderRadius: '0 0 16px 16px', display: 'block' }}
                src={`${storageApi.streamUrl(previewObj.id)}`}
              />
            ) : (
              <audio
                controls
                autoPlay
                style={{ width: '100%', margin: '2rem 0', display: 'block' }}
                src={`${storageApi.streamUrl(previewObj.id)}`}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};
