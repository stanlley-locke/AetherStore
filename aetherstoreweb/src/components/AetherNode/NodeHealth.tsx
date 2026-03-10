import React, { useState, useEffect } from 'react';
import { RefreshCcw, Zap, Globe, AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type StorageNode } from '../../services/api';

const fmtBytes = (b: number) => b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${(b / 1e6).toFixed(1)} MB`;
const fmtPct = (used: number, cap: number) => cap > 0 ? ((used / cap) * 100).toFixed(1) : '0';

type NodeHealth = {
    node: StorageNode;
    latencyMs: number;
    dhtPeers: number;
    storageHealth: 'good' | 'warn' | 'critical';
    networkStatus: 'stable' | 'degraded' | 'offline';
};

// Health data is now provided directly by the API

const statusColor = { stable: '#10b981', degraded: '#f59e0b', offline: '#ef4444', good: '#10b981', warn: '#f59e0b', critical: '#ef4444' };

export const NodeHealth: React.FC = () => {
    const { did } = useAuthStore();
    const [healths, setHealths] = useState<NodeHealth[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const r = await aetherNodeApi.getFleet(createAuthenticatedClient(did));
            const realHealths: NodeHealth[] = (r.data.nodes as any[]).map(n => ({
                node: n,
                latencyMs: n.latency_ms || (n.is_active ? 50 : 9999),
                dhtPeers: n.dht_peers || 0,
                storageHealth: n.used_bytes / n.capacity_bytes > 0.85 ? 'critical' : n.used_bytes / n.capacity_bytes > 0.65 ? 'warn' : 'good',
                networkStatus: !n.is_active ? 'offline' : n.uptime_pct < 70 ? 'degraded' : 'stable',
            }));
            setHealths(realHealths);
            setLastRefresh(new Date());
        } finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [did]);

    const online = healths.filter(h => h.networkStatus !== 'offline').length;
    const warnings = healths.filter(h => h.storageHealth !== 'good' || h.networkStatus === 'degraded').length;
    const critical = healths.filter(h => h.networkStatus === 'offline' || h.storageHealth === 'critical').length;
    const avgLatency = healths.filter(h => h.latencyMs < 9999).reduce((sum, h, _, arr) => sum + h.latencyMs / arr.length, 0);

    return (
        <div>
            {/* Network Health Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
                {[
                    { label: 'Online Nodes', value: online, icon: CheckCircle2, color: '#10b981' },
                    { label: 'Warnings', value: warnings, icon: AlertTriangle, color: '#f59e0b' },
                    { label: 'Critical', value: critical, icon: AlertTriangle, color: '#ef4444' },
                    { label: 'Avg Latency', value: `${avgLatency.toFixed(0)} ms`, icon: Zap, color: '#6366f1' },
                ].map(s => (
                    <div key={s.label} className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
                        <div style={{ width: 38, height: 38, borderRadius: 8, background: `${s.color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            <s.icon size={18} color={s.color} />
                        </div>
                        <div>
                            <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
                            <div style={{ fontSize: '1.3rem', fontWeight: 800, marginTop: 2 }}>{s.value}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Refresh bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem' }}>Node Diagnostics</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    {lastRefresh && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}><Clock size={13} />Last: {lastRefresh.toLocaleTimeString()}</span>}
                    <button onClick={load} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.875rem', border: '1px solid var(--border-color)', borderRadius: 8, background: 'transparent', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                        <RefreshCcw size={13} />Refresh
                    </button>
                </div>
            </div>

            {/* Health Cards */}
            {loading ? (
                <div className="loading-state"><RefreshCcw className="animate-spin" /><p>Running diagnostics...</p></div>
            ) : healths.length === 0 ? (
                <div className="glass-panel" style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    <Globe size={40} style={{ opacity: 0.3, margin: '0 auto 1rem', display: 'block' }} />
                    <p>No nodes to diagnose. Register a storage node first.</p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {healths.map(h => {
                        const netCol = statusColor[h.networkStatus];
                        const stCol = statusColor[h.storageHealth];
                        const usedPct = parseFloat(fmtPct(h.node.used_bytes, h.node.capacity_bytes));
                        return (
                            <div key={h.node.node_id} className="glass-panel" style={{ padding: '1.5rem' }}>
                                {/* Header */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.node.node_id}</div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}><Zap size={11} />{h.node.endpoint}</div>
                                    </div>
                                    <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                                        <span style={{ padding: '0.25rem 0.625rem', borderRadius: 20, fontSize: '0.7rem', fontWeight: 700, background: `${netCol}15`, color: netCol }}>{h.networkStatus.toUpperCase()}</span>
                                        <span style={{ padding: '0.25rem 0.625rem', borderRadius: 20, fontSize: '0.7rem', fontWeight: 700, background: `${stCol}15`, color: stCol }}>STORAGE {h.storageHealth.toUpperCase()}</span>
                                    </div>
                                </div>

                                {/* Metric Grid */}
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem' }}>
                                    {/* Latency */}
                                    <div>
                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Latency</div>
                                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.25rem' }}>
                                            <span style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'monospace', color: h.latencyMs > 100 ? '#f59e0b' : 'inherit' }}>{h.latencyMs === 9999 ? '—' : h.latencyMs}</span>
                                            {h.latencyMs !== 9999 && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ms</span>}
                                        </div>
                                    </div>

                                    {/* DHT Peers */}
                                    <div>
                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>DHT Peers</div>
                                        <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'monospace' }}>{h.dhtPeers}</div>
                                    </div>

                                    {/* Uptime */}
                                    <div>
                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Uptime</div>
                                        <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'monospace' }}>{h.node.uptime_pct}%</div>
                                    </div>

                                    {/* Reputation */}
                                    <div>
                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Reputation</div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            <div style={{ flex: 1, height: 6, background: 'var(--bg-hover)', borderRadius: 3 }}>
                                                <div style={{ height: '100%', width: `${h.node.reputation}%`, background: h.node.reputation > 70 ? '#10b981' : '#f59e0b', borderRadius: 3 }} />
                                            </div>
                                            <span style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'monospace', flexShrink: 0 }}>{h.node.reputation}</span>
                                        </div>
                                    </div>

                                    {/* Storage */}
                                    <div style={{ gridColumn: 'span 2' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                                            <span>Storage ({usedPct}%)</span>
                                            <span>{fmtBytes(h.node.used_bytes)} / {fmtBytes(h.node.capacity_bytes)}</span>
                                        </div>
                                        <div style={{ height: 8, background: 'var(--bg-hover)', borderRadius: 4 }}>
                                            <div style={{ height: '100%', width: `${usedPct}%`, background: stCol, borderRadius: 4, transition: 'width 0.5s' }} />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
