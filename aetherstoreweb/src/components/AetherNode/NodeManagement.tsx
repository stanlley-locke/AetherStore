import React, { useState, useEffect } from 'react';
import { Cpu, RefreshCcw, Plus, X, CheckCircle2, XCircle, Zap, AlertTriangle } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type StorageNode } from '../../services/api';

const fmtBytes = (b: number) => b > 1e9 ? `${(b / 1e9).toFixed(2)} GB` : `${(b / 1e6).toFixed(2)} MB`;
const fmtTs = (ts: string) => ts ? new Date(ts).toLocaleString() : 'Never';

export const NodeManagement: React.FC = () => {
    const { did } = useAuthStore();
    const [nodes, setNodes] = useState<StorageNode[]>([]);
    const [loading, setLoading] = useState(true);
    const [claimOpen, setClaimOpen] = useState(false);
    const [claimId, setClaimId] = useState('');
    const [claimEndpoint, setClaimEndpoint] = useState('');
    const [claiming, setClaiming] = useState(false);
    const [claimError, setClaimError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [search, setSearch] = useState('');

    const load = async () => {
        setLoading(true);
        try {
            const r = await aetherNodeApi.getFleet(createAuthenticatedClient(did));
            setNodes(r.data.nodes);
        } finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [did]);

    const handleClaim = async () => {
        if (!claimId.trim()) { setClaimError('Node ID is required'); return; }
        setClaiming(true); setClaimError(null);
        try {
            await aetherNodeApi.claimNode(createAuthenticatedClient(did), claimId.trim(), claimEndpoint.trim() || undefined);
            setClaimOpen(false); setClaimId(''); setClaimEndpoint('');
            setSuccess(`Node "${claimId.trim()}" claimed successfully.`);
            setTimeout(() => setSuccess(null), 4000);
            await load();
        } catch (e: any) {
            setClaimError(e.response?.data?.error || 'Failed to claim node');
        } finally { setClaiming(false); }
    };

    const filtered = nodes.filter(n =>
        n.node_id.toLowerCase().includes(search.toLowerCase()) ||
        n.endpoint.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div>
            {/* Toolbar */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
                <input
                    value={search} onChange={e => setSearch(e.target.value)}
                    placeholder="Search by node ID or endpoint..."
                    style={{ flex: 1, padding: '0.6rem 1rem', border: '1px solid var(--border-color)', borderRadius: 8, background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.875rem', outline: 'none' }}
                />
                <button onClick={load} style={{ padding: '0.6rem 1rem', border: '1px solid var(--border-color)', borderRadius: 8, background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', fontWeight: 600 }}>
                    <RefreshCcw size={15} /> Refresh
                </button>
                <button onClick={() => setClaimOpen(true)} style={{ padding: '0.6rem 1.1rem', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', fontWeight: 600 }}>
                    <Plus size={15} /> Claim Node
                </button>
            </div>

            {success && (
                <div style={{ padding: '0.75rem 1rem', background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 8, color: '#10b981', fontSize: '0.875rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <CheckCircle2 size={16} />{success}
                </div>
            )}

            {/* Node Table */}
            <div className="glass-panel" style={{ overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}>
                            {['Status', 'Node ID', 'Endpoint', 'Uptime', 'Capacity Used', 'Reputation', 'Last Heartbeat', ''].map(h => (
                                <th key={h} style={{ padding: '0.875rem 1rem', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr><td colSpan={8} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}><RefreshCcw style={{ animation: 'spin 1s linear infinite', display: 'inline' }} size={20} /></td></tr>
                        ) : filtered.length === 0 ? (
                            <tr><td colSpan={8} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>No nodes found. Claim your first node to get started.</td></tr>
                        ) : filtered.map(n => {
                            const usedPct = n.capacity_bytes > 0 ? (n.used_bytes / n.capacity_bytes * 100) : 0;
                            return (
                                <tr key={n.node_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                    <td style={{ padding: '1rem' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            {n.is_active ? <CheckCircle2 size={16} color="#10b981" /> : <XCircle size={16} color="#ef4444" />}
                                            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: n.is_active ? '#10b981' : '#ef4444' }}>{n.is_active ? 'Online' : 'Offline'}</span>
                                        </div>
                                    </td>
                                    <td style={{ padding: '1rem' }}>
                                        <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{n.node_id.slice(0, 20)}...</span>
                                    </td>
                                    <td style={{ padding: '1rem' }}>
                                        <span style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{n.endpoint}</span>
                                    </td>
                                    <td style={{ padding: '1rem', fontWeight: 700 }}>{n.uptime_pct}%</td>
                                    <td style={{ padding: '1rem', minWidth: 160 }}>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>{fmtBytes(n.used_bytes)} / {fmtBytes(n.capacity_bytes)}</div>
                                        <div style={{ height: 5, background: 'var(--bg-hover)', borderRadius: 3 }}>
                                            <div style={{ height: '100%', width: `${usedPct}%`, background: usedPct > 85 ? '#ef4444' : 'var(--accent-primary)', borderRadius: 3 }} />
                                        </div>
                                    </td>
                                    <td style={{ padding: '1rem' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                            <div style={{ width: '100%', maxWidth: 60, height: 5, background: 'var(--bg-hover)', borderRadius: 3 }}>
                                                <div style={{ height: '100%', width: `${n.reputation}%`, background: n.reputation > 70 ? '#10b981' : '#f59e0b', borderRadius: 3 }} />
                                            </div>
                                            <span style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{n.reputation}</span>
                                        </div>
                                    </td>
                                    <td style={{ padding: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{fmtTs(n.last_heartbeat)}</td>
                                    <td style={{ padding: '1rem' }}>
                                        <button style={{ padding: '0.375rem 0.75rem', border: '1px solid var(--border-color)', borderRadius: 6, background: 'transparent', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                                            Details
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Claim Modal */}
            {claimOpen && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                    <div className="glass-panel" style={{ width: '100%', maxWidth: 460, padding: '2rem', margin: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <div>
                                <h3 style={{ margin: 0, fontWeight: 700 }}>Claim a Storage Node</h3>
                                <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>Link a headless node to your wallet profile</p>
                            </div>
                            <button onClick={() => { setClaimOpen(false); setClaimError(null); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}><X size={20} /></button>
                        </div>
                        {claimError && <div style={{ padding: '0.75rem', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, color: '#ef4444', fontSize: '0.875rem', marginBottom: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}><AlertTriangle size={15} />{claimError}</div>}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            {[{ label: 'Node ID *', val: claimId, set: setClaimId, ph: 'node_abc123...' }, { label: 'Endpoint URL (optional)', val: claimEndpoint, set: setClaimEndpoint, ph: 'http://192.168.1.1:8080' }].map(f => (
                                <div key={f.label}>
                                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>{f.label}</label>
                                    <input value={f.val} onChange={e => f.set(e.target.value)} placeholder={f.ph}
                                        style={{ width: '100%', padding: '0.625rem 0.875rem', border: '1px solid var(--border-color)', borderRadius: 8, background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.875rem', boxSizing: 'border-box', outline: 'none', fontFamily: 'monospace' }} />
                                </div>
                            ))}
                            <button onClick={handleClaim} disabled={claiming}
                                style={{ padding: '0.75rem', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 8, fontWeight: 700, cursor: 'pointer', fontSize: '0.9rem' }}>
                                {claiming ? 'Claiming...' : 'Claim Node'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
