import React, { useState, useEffect } from 'react';
import { BarChart3, RefreshCcw, TrendingUp, Coins, Award, Clock } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type EarningsResponse } from '../../services/api';

const fmtATK = (n: number) => n.toFixed(4);

export const MiningRewards: React.FC = () => {
    const { did } = useAuthStore();
    const [earnings, setEarnings] = useState<EarningsResponse | null>(null);
    const [loading, setLoading] = useState(true);

    const load = async () => {
        setLoading(true);
        try {
            const r = await aetherNodeApi.getEarnings(createAuthenticatedClient(did));
            setEarnings(r.data);
        } finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [did]);

    const history = earnings?.recent_history ?? [];
    // Compute bar chart heights relative to max
    const maxReward = history.length > 0 ? Math.max(...history.map(h => h.amount)) : 1;

    return (
        <div>
            {/* Stat Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
                {[
                    { label: 'Total Earned', value: `${fmtATK(earnings?.total_earned ?? 0)} ATK`, icon: Coins, color: '#10b981' },
                    { label: 'Avg. Reward', value: `${fmtATK(earnings?.avg_reward ?? 0)} ATK`, icon: TrendingUp, color: '#6366f1' },
                    { label: 'Reward Events', value: earnings?.reward_count ?? 0, icon: Award, color: '#f59e0b' },
                ].map(s => (
                    <div key={s.label} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{ width: 44, height: 44, borderRadius: 10, background: `${s.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            <s.icon size={20} color={s.color} />
                        </div>
                        <div>
                            <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
                            <div style={{ fontSize: '1.4rem', fontWeight: 800, marginTop: 2, fontFamily: 'monospace' }}>{s.value}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Mini Bar Chart */}
            {history.length > 0 && (
                <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                        <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem' }}>Reward History</h3>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Last {history.length} events</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.375rem', height: 120 }}>
                        {[...history].reverse().slice(0, 30).map((h, i) => {
                            const barH = Math.max(4, (h.amount / maxReward) * 100);
                            return (
                                <div key={i} title={`${fmtATK(h.amount)} ATK`}
                                    style={{ flex: 1, height: `${barH}%`, background: 'var(--accent-primary)', borderRadius: '2px 2px 0 0', opacity: 0.85, minWidth: 4, cursor: 'default', transition: 'opacity 0.2s' }}
                                />
                            );
                        })}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        <span>Oldest</span><span>Newest</span>
                    </div>
                </div>
            )}

            {/* Recent History Table */}
            <div className="glass-panel" style={{ overflow: 'hidden' }}>
                <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem' }}>Recent Reward Events</h3>
                    <button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.8rem' }}>
                        <RefreshCcw size={14} /> Refresh
                    </button>
                </div>
                {loading ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}><RefreshCcw style={{ animation: 'spin 1s linear infinite' }} size={20} /></div>
                ) : history.length === 0 ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <BarChart3 size={32} style={{ opacity: 0.3, margin: '0 auto 0.75rem', display: 'block' }} />
                        <p style={{ margin: 0 }}>No rewards recorded yet. Start your node to earn ATK.</p>
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                        <thead>
                            <tr style={{ background: 'var(--bg-secondary)' }}>
                                {['Node ID', 'Type', 'Amount (ATK)', 'Timestamp'].map(h => (
                                    <th key={h} style={{ padding: '0.875rem 1.25rem', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {history.map((r, i) => (
                                <tr key={i} style={{ borderTop: '1px solid var(--border-color)' }}>
                                    <td style={{ padding: '0.875rem 1.25rem', fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{r.node_id?.slice(0, 20)}...</td>
                                    <td style={{ padding: '0.875rem 1.25rem' }}>
                                        <span style={{ padding: '0.2rem 0.625rem', borderRadius: 20, fontSize: '0.7rem', fontWeight: 700, background: 'rgba(99,102,241,0.1)', color: '#6366f1' }}>{r.type}</span>
                                    </td>
                                    <td style={{ padding: '0.875rem 1.25rem', fontFamily: 'monospace', fontWeight: 700, color: '#10b981' }}>+{fmtATK(r.amount)}</td>
                                    <td style={{ padding: '0.875rem 1.25rem', fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                        <Clock size={12} />{new Date(r.timestamp).toLocaleString()}
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
