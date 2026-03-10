import React, { useState, useEffect } from 'react';
import { Zap, AlertCircle, RefreshCcw, Terminal, X, Wifi } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type StorageNode } from '../../services/api';

interface LogEntry {
    timestamp: string;
    level: 'info' | 'warn' | 'error';
    message: string;
}

export const FleetManager: React.FC = () => {
    const { did } = useAuthStore();
    const [nodes, setNodes] = useState<StorageNode[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeLogsNodeId, setActiveLogsNodeId] = useState<string | null>(null);
    const [logs, setLogs] = useState<LogEntry[]>([]);

    const generateFakeLog = (nodeId: string): LogEntry => {
        const events = [
            `Kademlia DHT: Routing table refreshed. Found 4 new neighbors.`,
            `Proof-of-Service: Challenge RECEIVED from 0x71...f2e.`,
            `Proof-of-Service: Validated shard 0x${Math.random().toString(16).slice(2, 10)}.`,
            `Storage: Received 256KB block for bucket 'media'.`,
            `Heartbeat: Pulse sent to bootstrap node at 142.250.190.46.`,
            `Network: WebSocket connection stabilized. Latency: ${Math.floor(Math.random() * 50) + 10}ms.`,
            `Security: DID signature validated for incoming request.`
        ];
        return {
            timestamp: new Date().toLocaleTimeString(),
            level: Math.random() > 0.9 ? 'warn' : 'info',
            message: events[Math.floor(Math.random() * events.length)]
        };
    };

    useEffect(() => {
        if (!activeLogsNodeId) {
            setLogs([]);
            return;
        }

        // Initial logs
        setLogs(Array.from({ length: 5 }, () => generateFakeLog(activeLogsNodeId)));

        const interval = setInterval(() => {
            setLogs(prev => [generateFakeLog(activeLogsNodeId), ...prev].slice(0, 50));
        }, 3000);

        return () => clearInterval(interval);
    }, [activeLogsNodeId]);

    const loadFleet = async () => {
        setLoading(true);
        try {
            const client = createAuthenticatedClient(did);
            const response = await aetherNodeApi.getFleet(client);
            setNodes(response.data.nodes);
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to load fleet');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadFleet();
    }, [did]);

    if (loading && nodes.length === 0) {
        return (
            <div className="loading-state">
                <RefreshCcw className="animate-spin" />
                <p>Syncing fleet status...</p>
            </div>
        );
    }

    return (
        <div className="fleet-manager">
            <div className="node-grid">
                {nodes.map((node: StorageNode) => (
                    <div key={node.node_id} className="node-card glass-panel">
                        <div className="node-card-header">
                            <div className={`status-dot ${node.is_active ? 'online' : 'offline'}`}></div>
                            <span className="node-id font-mono text-xs">{node.node_id.slice(0, 16)}...</span>
                            <span className={`status-badge ${node.is_active ? 'online' : 'offline'}`}>
                                {node.is_active ? 'Active' : 'Offline'}
                            </span>
                        </div>

                        <div className="node-card-body">
                            <div className="metric-row">
                                <div className="metric">
                                    <label>Uptime</label>
                                    <span className="value">{node.uptime_pct}%</span>
                                </div>
                                <div className="metric">
                                    <label>Reputation</label>
                                    <span className="value">{node.reputation}/100</span>
                                </div>
                            </div>

                            <div className="capacity-section">
                                <div className="capacity-labels">
                                    <label>Capacity Usage</label>
                                    <span>{(node.used_bytes / 1024 / 1024).toFixed(2)} MB / {(node.capacity_bytes / 1024 / 1024).toFixed(2)} MB</span>
                                </div>
                                <div className="progress-bar-bg">
                                    <div 
                                        className="progress-bar-fill" 
                                        style={{ width: `${(node.used_bytes / node.capacity_bytes) * 100 || 0}%` }}
                                    ></div>
                                </div>
                            </div>

                            <div className="endpoint-info">
                                <Zap size={14} />
                                <span>{node.endpoint}</span>
                            </div>
                        </div>

                        <div className="node-card-footer">
                            <button 
                                className="node-action-btn"
                                onClick={() => setActiveLogsNodeId(node.node_id)}
                            >
                                View Logs
                            </button>
                            <button className="node-action-btn primary">Configure</button>
                        </div>
                    </div>
                ))}

                <div className="add-node-card glass-panel dashed">
                    <AlertCircle size={32} className="text-muted" />
                    <p>Register a new storage node to start mining ATK</p>
                    <button className="claim-link-btn">How to host a node?</button>
                </div>
            </div>

            {/* Log Viewer Overlay */}
            {activeLogsNodeId && (
                <div className="log-overlay">
                    <div className="log-modal glass-panel">
                        <div className="modal-header">
                            <div className="title">
                                <Terminal size={18} />
                                <h3>Node Log Stream: <span className="font-mono">{activeLogsNodeId.slice(0, 16)}...</span></h3>
                            </div>
                            <div className="status-indicator">
                                <div className="pulse-dot"></div>
                                <span>LIVE</span>
                                <button className="close-btn" onClick={() => setActiveLogsNodeId(null)}>
                                    <X size={20} />
                                </button>
                            </div>
                        </div>
                        <div className="log-body font-mono">
                            {logs.map((log: LogEntry, i: number) => (
                                <div key={i} className={`log-line ${log.level}`}>
                                    <span className="ts">[{log.timestamp}]</span>
                                    <span className="lvl">{log.level.toUpperCase()}</span>
                                    <span className="msg">{log.message}</span>
                                </div>
                            ))}
                        </div>
                        <div className="modal-footer">
                            <div className="net-stat">
                                <Wifi size={14} />
                                <span>Kademlia DHT Connection: STABLE</span>
                            </div>
                            <p className="hint">Simulation: Streaming real-time node activity</p>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                .node-card {
                    padding: 1.5rem;
                    display: flex;
                    flex-direction: column;
                    gap: 1.25rem;
                }
                .node-card-header {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                }
                .status-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                }
                .status-dot.online { background: #10b981; box-shadow: 0 0 8px #10b981; }
                .status-dot.offline { background: #ef4444; }
                .node-id { color: var(--text-muted); flex: 1; }
                .status-badge {
                    font-size: 0.7rem;
                    padding: 0.25rem 0.625rem;
                    border-radius: 20px;
                    font-weight: 700;
                    text-transform: uppercase;
                }
                .status-badge.online { background: rgba(16, 185, 129, 0.1); color: #10b981; }
                .status-badge.offline { background: rgba(239, 44, 44, 0.1); color: #ef4444; }
                .metric-row { display: flex; gap: 2rem; }
                .metric label { display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem; }
                .metric .value { font-size: 1.1rem; font-weight: 700; font-family: var(--font-mono); }
                .capacity-section { margin-top: 0.5rem; }
                .capacity-labels { display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 0.5rem; color: var(--text-muted); }
                .progress-bar-bg { height: 6px; background: var(--bg-hover); border-radius: 3px; overflow: hidden; }
                .progress-bar-fill { height: 100%; background: var(--accent-primary); border-radius: 3px; }
                .endpoint-info { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; }
                .node-card-footer { display: flex; gap: 0.75rem; margin-top: 0.5rem; }
                .node-action-btn { flex: 1; padding: 0.625rem; border-radius: 8px; border: 1px solid var(--border-color); background: transparent; color: var(--text-primary); cursor: pointer; font-size: 0.85rem; font-weight: 600; transition: all 0.2s; }
                .node-action-btn:hover { background: var(--bg-hover); }
                .node-action-btn.primary { background: var(--accent-primary); border-color: var(--accent-primary); color: white; }
                .add-node-card { border-style: dashed; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 1rem; color: var(--text-muted); min-height: 200px; }
                .claim-link-btn { color: var(--accent-primary); background: none; border: none; font-weight: 600; cursor: pointer; text-decoration: underline; }

                /* Log Viewer Styles */
                .log-overlay {
                    position: fixed;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background: rgba(0, 0, 0, 0.7);
                    backdrop-filter: blur(4px);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                    padding: 2rem;
                }
                .log-modal {
                    width: 100%;
                    max-width: 800px;
                    height: 500px;
                    display: flex;
                    flex-direction: column;
                    background: #0f172a; /* Solid dark for terminal feel */
                    border: 1px solid var(--accent-primary);
                }
                .modal-header {
                    padding: 1rem 1.5rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                }
                .modal-header .title { display: flex; align-items: center; gap: 0.75rem; color: #f8fafc; }
                .modal-header h3 { margin: 0; font-size: 1rem; }
                .status-indicator { display: flex; align-items: center; gap: 0.75rem; color: #10b981; font-weight: 800; font-size: 0.8rem; }
                .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #10b981; animation: pulse 1.5s infinite; }
                @keyframes pulse { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(1.2); } 100% { opacity: 1; transform: scale(1); } }
                .close-btn { background: none; border: none; color: #94a3b8; cursor: pointer; display: flex; align-items: center; }
                .close-btn:hover { color: #f8fafc; }
                .log-body { flex: 1; overflow-y: auto; padding: 1.5rem; display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem; color: #cbd5e1; }
                .log-line { display: flex; gap: 0.75rem; }
                .log-line.warn { color: #fbbf24; }
                .log-line.error { color: #ef4444; }
                .log-line .ts { color: #64748b; min-width: 80px; }
                .log-line .lvl { min-width: 45px; font-weight: 800; }
                .modal-footer { padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255, 255, 255, 0.1); background: rgba(0,0,0,0.2); }
                .net-stat { display: flex; align-items: center; gap: 0.5rem; color: #64748b; font-size: 0.75rem; }
                .hint { font-size: 0.75rem; color: #475569; margin: 0; font-style: italic; }
            `}</style>
        </div>
    );
};
