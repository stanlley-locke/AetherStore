import React, { useState, useEffect } from 'react';
import { Banknote, RefreshCcw, CheckCircle2, AlertTriangle, Coins, TrendingUp, ArrowDownToLine } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type EarningsResponse } from '../../services/api';

const fmtATK = (n: number) => n.toFixed(6);

export const PayoutHistory: React.FC = () => {
    const { did } = useAuthStore();
    const [earnings, setEarnings] = useState<EarningsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [payingOut, setPayingOut] = useState(false);
    const [payoutResult, setPayoutResult] = useState<{ success: boolean; message: string } | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const r = await aetherNodeApi.getEarnings(createAuthenticatedClient(did));
            setEarnings(r.data);
        } finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [did]);

    const handlePayout = async () => {
        setPayingOut(true); setPayoutResult(null);
        try {
            const r = await aetherNodeApi.payout(createAuthenticatedClient(did));
            setPayoutResult({ success: true, message: (r.data as any).message || 'Payout completed successfully.' });
            await load();
        } catch (e: any) {
            setPayoutResult({ success: false, message: e.response?.data?.error || 'Payout failed. Please try again.' });
        } finally { setPayingOut(false); }
    };

    const history = earnings?.recent_history ?? [];
    const claimable = earnings?.total_earned ?? 0;

    return (
        <div>
            {/* Payout Card */}
            <div className="glass-panel" style={{ padding: '2rem', marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '2rem', flexWrap: 'wrap' }}>
                <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.5rem' }}>Available to Withdraw</div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                        <span style={{ fontSize: '2.25rem', fontWeight: 800, fontFamily: 'monospace' }}>{fmtATK(claimable)}</span>
                        <span style={{ fontSize: '1rem', color: 'var(--text-muted)', fontWeight: 700 }}>ATK</span>
                    </div>
                    <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>Across {earnings?.reward_count ?? 0} reward events</div>
                </div>

                <button
                    onClick={handlePayout}
                    disabled={payingOut || claimable === 0}
                    style={{
                        display: 'flex', alignItems: 'center', gap: '0.5rem',
                        padding: '0.875rem 2rem', background: claimable > 0 ? 'var(--accent-primary)' : 'var(--bg-hover)',
                        color: claimable > 0 ? 'white' : 'var(--text-muted)', border: 'none', borderRadius: 10,
                        fontWeight: 700, fontSize: '0.95rem', cursor: claimable > 0 ? 'pointer' : 'not-allowed'
                    }}
                >
                    <ArrowDownToLine size={18} />
                    {payingOut ? 'Processing...' : 'Withdraw All Earnings'}
                </button>
            </div>

            {/* Result Banner */}
            {payoutResult && (
                <div style={{
                    padding: '0.875rem 1.25rem', borderRadius: 8, marginBottom: '1.5rem',
                    background: payoutResult.success ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                    border: `1px solid ${payoutResult.success ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                    color: payoutResult.success ? '#10b981' : '#ef4444', display: 'flex', alignItems: 'center', gap: '0.625rem', fontSize: '0.875rem'
                }}>
                    {payoutResult.success ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                    {payoutResult.message}
                </div>
            )}

            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
                {[
                    { label: 'Total Earned', value: `${fmtATK(earnings?.total_earned ?? 0)} ATK`, icon: Coins, color: '#10b981' },
                    { label: 'Avg per Event', value: `${fmtATK(earnings?.avg_reward ?? 0)} ATK`, icon: TrendingUp, color: '#6366f1' },
                    { label: 'Total Events', value: earnings?.reward_count ?? 0, icon: Banknote, color: '#f59e0b' },
                ].map(s => (
                    <div key={s.label} className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
                        <div style={{ width: 40, height: 40, borderRadius: 9, background: `${s.color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            <s.icon size={18} color={s.color} />
                        </div>
                        <div>
                            <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
                            <div style={{ fontSize: '1.1rem', fontWeight: 800, fontFamily: 'monospace', marginTop: 2 }}>{s.value}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* History Table */}
            <div className="glass-panel" style={{ overflow: 'hidden' }}>
                <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem' }}>Payout Ledger</h3>
                    <button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.8rem' }}>
                        <RefreshCcw size={14} /> Refresh
                    </button>
                </div>
                {loading ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}><RefreshCcw size={20} style={{ animation: 'spin 1s linear infinite' }} /></div>
                ) : history.length === 0 ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <Banknote size={32} style={{ opacity: 0.3, display: 'block', margin: '0 auto 0.75rem' }} />
                        <p style={{ margin: 0 }}>No payout history yet.</p>
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                        <thead>
                            <tr style={{ background: 'var(--bg-secondary)' }}>
                                {['#', 'Node', 'Reward Type', 'Amount', 'Date'].map(h => (
                                    <th key={h} style={{ padding: '0.875rem 1.25rem', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {history.map((r, i) => (
                                <tr key={i} style={{ borderTop: '1px solid var(--border-color)' }}>
                                    <td style={{ padding: '0.875rem 1.25rem', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: '0.8rem' }}>#{i + 1}</td>
                                    <td style={{ padding: '0.875rem 1.25rem', fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{r.node_id?.slice(0, 18)}...</td>
                                    <td style={{ padding: '0.875rem 1.25rem' }}>
                                        <span style={{ padding: '0.2rem 0.625rem', borderRadius: 20, fontSize: '0.7rem', fontWeight: 700, background: 'rgba(99,102,241,0.1)', color: '#6366f1' }}>{r.type}</span>
                                    </td>
                                    <td style={{ padding: '0.875rem 1.25rem', fontFamily: 'monospace', fontWeight: 700, color: '#10b981', fontSize: '0.9rem' }}>+{fmtATK(r.amount)} ATK</td>
                                    <td style={{ padding: '0.875rem 1.25rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{new Date(r.timestamp).toLocaleString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};
