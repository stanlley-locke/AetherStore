import React, { useState, useEffect } from 'react';
import {
    Server, RefreshCcw, Plus, Globe, CheckCircle2,
    XCircle, Cpu, Database, Terminal, X, Wifi, Zap
} from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type FleetResponse } from '../../services/api';

interface LogEntry { timestamp: string; level: 'info' | 'warn' | 'error'; message: string; }

const fmtBytes = (b: number) => b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${(b / 1e6).toFixed(1)} MB`;



export const FleetOverview: React.FC = () => {
    const { did } = useAuthStore();
    const [fleet, setFleet] = useState<FleetResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [logsNodeId, setLogsNodeId] = useState<string | null>(null);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [claimOpen, setClaimOpen] = useState(false);
    const [claimId, setClaimId] = useState('');
    const [claimEndpoint, setClaimEndpoint] = useState('');
    const [claiming, setClaiming] = useState(false);
    const [claimError, setClaimError] = useState<string | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const r = await aetherNodeApi.getFleet(createAuthenticatedClient(did));
            setFleet(r.data);
        } finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [did]);

    useEffect(() => {
        if (!logsNodeId) { setLogs([]); return; }
        
        const fetchNodeLogs = async () => {
            try {
                const client = createAuthenticatedClient(did);
                const r = await aetherNodeApi.getNodeLogs(client, logsNodeId, 60);
                const mapped: LogEntry[] = r.data.logs.map((raw) => {
                    // 2026-03-09 14:22:54 - INFO - message
                    const parts = raw.split(' - ');
                    if (parts.length >= 3) {
                        return { 
                            timestamp: parts[0], 
                            level: parts[1].toLowerCase() as any, 
                            message: parts.slice(2).join(' - ') 
                        };
                    }
                    return { timestamp: '', level: 'info', message: raw };
                });
                setLogs(mapped.reverse()); // Reverse to keep newest at top
            } catch (e) {
                console.error('Failed to fetch node logs', e);
            }
        };

        fetchNodeLogs();
        const iv = setInterval(fetchNodeLogs, 3000);
        return () => clearInterval(iv);
    }, [logsNodeId, did]);

    const handleClaim = async () => {
        if (!claimId.trim()) { setClaimError('Node ID is required'); return; }
        setClaiming(true); setClaimError(null);
        try {
            await aetherNodeApi.claimNode(createAuthenticatedClient(did), claimId, claimEndpoint || undefined);
            setClaimOpen(false); setClaimId(''); setClaimEndpoint('');
            await load();
        } catch (e: any) {
            setClaimError(e.response?.data?.error || 'Failed to claim node');
        } finally { setClaiming(false); }
    };

    const nodes = fleet?.nodes ?? [];
    const activeCount = nodes.filter(n => n.is_active).length;

    return (
        <div>
            {/* Summary Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
                {[
                    { label: 'Total Nodes', value: fleet?.fleet_count ?? 0, icon: Server, color: '#6366f1' },
                    { label: 'Online', value: activeCount, icon: CheckCircle2, color: '#10b981' },
                    { label: 'Offline', value: nodes.length - activeCount, icon: XCircle, color: '#ef4444' },
                    { label: 'Total Capacity', value: fmtBytes(fleet?.total_capacity_bytes ?? 0), icon: Database, color: '#6366f1' },
                    { label: 'Used Storage', value: fmtBytes(fleet?.total_used_bytes ?? 0), icon: Cpu, color: '#f59e0b' },
                ].map(s => (
                    <div key={s.label} className="glass-panel" style={{ padding: '1.25rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <div style={{ width: 38, height: 38, borderRadius: 8, background: `${s.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                <s.icon size={18} color={s.color} />
                            </div>
                            <div>
                                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: 2 }}>{s.value}</div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Claim Button */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1.25rem' }}>
                <button
                    onClick={() => setClaimOpen(true)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.1rem', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}
                >
                    <Plus size={16} /> Claim Node
                </button>
            </div>

            {/* Node Grid */}
            {loading && nodes.length === 0 ? (
                <div className="loading-state"><RefreshCcw className="animate-spin" /><p>Syncing fleet...</p></div>
            ) : nodes.length === 0 ? (
                <div className="glass-panel" style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    <Globe size={40} style={{ margin: '0 auto 1rem', display: 'block', opacity: 0.3 }} />
                    <p>No nodes registered yet. Claim your first node to start mining ATK.</p>
                </div>
            ) : (
                <div className="node-grid">
                    {nodes.map(node => {
                        const usedPct = node.capacity_bytes > 0 ? (node.used_bytes / node.capacity_bytes) * 100 : 0;
                        return (
                            <div key={node.node_id} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: node.is_active ? '#10b981' : '#ef4444', boxShadow: node.is_active ? '0 0 8px #10b981' : 'none', flexShrink: 0 }} />
                                    <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.node_id}</span>
                                    <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: 20, background: node.is_active ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', color: node.is_active ? '#10b981' : '#ef4444' }}>
                                        {node.is_active ? 'ONLINE' : 'OFFLINE'}
                                    </span>
                                </div>

                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                                    {[
                                        ['Uptime', `${node.uptime_pct}%`], 
                                        ['Reputation', `${node.reputation}/100`],
                                        ['Latency', node.latency_ms ? `${node.latency_ms} ms` : '—'],
                                        ['DHT Peers', node.dht_peers ?? '—']
                                    ].map(([l, v]) => (
                                        <div key={l}>
                                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{l}</div>
                                            <div style={{ fontWeight: 700, fontFamily: 'monospace' }}>{v}</div>
                                        </div>
                                    ))}
                                </div>

                                <div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                                        <span>Storage</span>
                                        <span>{fmtBytes(node.used_bytes)} / {fmtBytes(node.capacity_bytes)}</span>
                                    </div>
                                    <div style={{ height: 6, background: 'var(--bg-hover)', borderRadius: 3, overflow: 'hidden' }}>
                                        <div style={{ height: '100%', width: `${usedPct}%`, background: usedPct > 85 ? '#ef4444' : 'var(--accent-primary)', borderRadius: 3 }} />
                                    </div>
                                </div>

                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                    <Zap size={12} />{node.endpoint}
                                </div>

                                <div style={{ display: 'flex', gap: '0.6rem' }}>
                                    <button onClick={() => setLogsNodeId(node.node_id)}
                                        style={{ flex: 1, padding: '0.55rem', border: '1px solid var(--border-color)', background: 'transparent', borderRadius: 8, cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                        <Terminal size={13} style={{ display: 'inline', marginRight: 4 }} />Logs
                                    </button>
                                    <button style={{ flex: 1, padding: '0.55rem', border: '1px solid var(--accent-primary)', background: 'var(--accent-primary)', borderRadius: 8, cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: 'white' }}>
                                        Configure
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Claim Modal */}
            {claimOpen && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                    <div className="glass-panel" style={{ width: '100%', maxWidth: 460, padding: '2rem', margin: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Claim a Storage Node</h3>
                            <button onClick={() => setClaimOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}><X size={20} /></button>
                        </div>
                        {claimError && <div style={{ padding: '0.75rem', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, color: '#ef4444', fontSize: '0.875rem', marginBottom: '1rem' }}>{claimError}</div>}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>Node ID *</label>
                                <input value={claimId} onChange={e => setClaimId(e.target.value)} placeholder="node_abc123..." style={{ width: '100%', padding: '0.625rem 0.875rem', border: '1px solid var(--border-color)', borderRadius: 8, background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.875rem', boxSizing: 'border-box', outline: 'none', fontFamily: 'monospace' }} />
                            </div>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>Endpoint (optional)</label>
                                <input value={claimEndpoint} onChange={e => setClaimEndpoint(e.target.value)} placeholder="http://192.168.1.1:8080" style={{ width: '100%', padding: '0.625rem 0.875rem', border: '1px solid var(--border-color)', borderRadius: 8, background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.875rem', boxSizing: 'border-box', outline: 'none', fontFamily: 'monospace' }} />
                            </div>
                            <button onClick={handleClaim} disabled={claiming} style={{ padding: '0.75rem', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 8, fontWeight: 700, cursor: 'pointer', fontSize: '0.9rem' }}>
                                {claiming ? 'Claiming...' : 'Claim Node'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Log Terminal Modal */}
            {logsNodeId && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '2rem' }}>
                    <div style={{ width: '100%', maxWidth: 860, height: 520, display: 'flex', flexDirection: 'column', background: '#0f172a', border: '1px solid var(--accent-primary)', borderRadius: 12 }}>
                        <div style={{ padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#f8fafc' }}>
                                <Terminal size={18} color="var(--accent-primary)" />
                                <span style={{ fontWeight: 700 }}>Log Stream</span>
                                <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#64748b' }}>{logsNodeId.slice(0, 20)}...</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', fontSize: '0.75rem', fontWeight: 800 }}>
                                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#10b981', animation: 'pulse 1.5s infinite' }} />LIVE
                                </div>
                                <button onClick={() => setLogsNodeId(null)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', display: 'flex' }}><X size={20} /></button>
                            </div>
                        </div>
                        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', fontFamily: 'monospace', fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                            {logs.map((log, i) => (
                                <div key={i} style={{ display: 'flex', gap: '0.75rem', color: log.level === 'warn' ? '#fbbf24' : log.level === 'error' ? '#ef4444' : '#cbd5e1' }}>
                                    <span style={{ color: '#475569', minWidth: 80, flexShrink: 0 }}>[{log.timestamp}]</span>
                                    <span style={{ minWidth: 45, fontWeight: 800, flexShrink: 0 }}>{log.level.toUpperCase()}</span>
                                    <span>{log.message}</span>
                                </div>
                            ))}
                        </div>
                        <div style={{ padding: '0.875rem 1.5rem', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#475569', fontSize: '0.75rem' }}>
                            <Wifi size={13} /><span>Kademlia DHT: STABLE</span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
