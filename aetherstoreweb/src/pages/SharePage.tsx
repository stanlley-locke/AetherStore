import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { storageApi } from '../services/api';
import { FileText, Download, AlertCircle, Activity, Globe } from 'lucide-react';
import './SharePage.css';

export const SharePage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [fileInfo, setFileInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    
    const fetchInfo = async () => {
      try {
        const res = await storageApi.getPresignedInfo(token);
        setFileInfo(res.data);
      } catch (err: any) {
        if (err.response?.status === 404) {
          setError('File not found or link has expired.');
        } else {
          setError(err.response?.data?.error || 'Failed to load file information.');
        }
      } finally {
        setLoading(false);
      }
    };
    
    fetchInfo();
  }, [token]);

  if (loading) {
    return (
      <div className="share-page-container centered">
        <Activity size={48} className="spinner-icon" color="var(--accent)" />
        <h2 style={{marginTop: '1rem', color: 'var(--text-primary)', fontWeight: 500}}>Decrypting Link...</h2>
      </div>
    );
  }

  if (error || !fileInfo) {
    return (
      <div className="share-page-container centered">
        <div className="share-card error-card glass-panel">
          <AlertCircle size={48} color="var(--error)" style={{marginBottom: '1rem'}} />
          <h2 style={{color: 'var(--text-primary)'}}>Link Invalid</h2>
          <p style={{color: 'var(--text-secondary)'}}>{error}</p>
        </div>
      </div>
    );
  }

  const isMedia = fileInfo.mime_type?.startsWith('video/') || fileInfo.mime_type?.startsWith('audio/');
  // Prepend backend port if in DEV
  const backendPort = import.meta.env.DEV ? '8000' : window.location.port;
  const origin = `${window.location.protocol}//${window.location.hostname}:${backendPort}`;
  const streamUrl = `${origin}/api/v1/download/presigned/${token}/`;

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="share-page-container">
      <div className="share-nav">
        <div className="brand">
          <div className="logo-icon"><Globe size={24} color="#fff" /></div>
          <span className="logo-text">AetherDrive Share</span>
        </div>
      </div>
      
      <div className="share-content flex-center">
        <div className="share-card glass-panel bounce-in">
          <div className="file-preview">
            {isMedia ? (
              fileInfo.mime_type.startsWith('video/') ? (
                <video src={streamUrl} controls className="media-player" preload="metadata" />
              ) : (
                <audio src={streamUrl} controls className="media-player" preload="metadata" />
              )
            ) : (
              <div className="generic-preview">
                <FileText size={72} color="var(--accent)" className="file-icon" />
              </div>
            )}
          </div>
          
          <div className="file-details">
            <h1 className="share-filename" title={fileInfo.filename || fileInfo.id}>
              {fileInfo.filename || fileInfo.id}
            </h1>
            <div className="share-meta">
              <span>{formatSize(fileInfo.size)}</span>
              <span className="dot-separator">•</span>
              <span>{fileInfo.mime_type}</span>
            </div>
            
            <a href={streamUrl} download className="drive-btn-primary download-btn full-width" style={{marginTop: '2rem', justifyContent: 'center', height: '48px', fontSize: '1rem'}}>
              <Download size={20} /> Download Source File
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
