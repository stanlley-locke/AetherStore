import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Award, RefreshCcw, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type MiningReward } from '../../services/api';

export const MiningStats: React.FC = () => {
    const { did } = useAuthStore();
    const [stats, setStats] = useState<{
        total_earned: number;
        avg_reward: number;
        reward_count: number;
        recent_history: MiningReward[];
    } | null>(null);
    const [loading, setLoading] = useState(true);
    const [payoutLoading, setPayoutLoading] = useState(false);
    const [payoutSuccess, setPayoutSuccess] = useState(false);

    const loadStats = async () => {
        setLoading(true);
        try {
            const client = createAuthenticatedClient(did);
            const response = await aetherNodeApi.getEarnings(client);
            setStats(response.data);
        } catch (err) {
            console.error('Failed to load mining stats', err);
        } finally {
            setLoading(false);
        }
    };

    const handlePayout = async () => {
        if (!stats || stats.total_earned <= 0) return;
        
        setPayoutLoading(true);
        try {
            const client = createAuthenticatedClient(did);
            await aetherNodeApi.payout(client);
            setPayoutSuccess(true);
            setTimeout(() => setPayoutSuccess(false), 3000);
            await loadStats(); // Refresh
        } catch (err) {
            console.error('Payout failed', err);
            alert('Payout failed. No pending rewards or server error.');
        } finally {
            setPayoutLoading(false);
        }
    };

    useEffect(() => {
        loadStats();
    }, [did]);

    if (loading && !stats) {
        return (
            <div className="loading-state">
                <RefreshCcw className="animate-spin" />
                <p>Loading financial data...</p>
            </div>
        );
    }

    return (
        <div className="mining-stats">
            <div className="stats-container">
                <div className="stat-card glass-panel highlight">
                    <div className="stat-icon-wrapper">
                        <TrendingUp size={24} />
                    </div>
                    <div className="stat-details">
                        <label>Total ATK Mined</label>
                        <div className="stat-value font-mono">{(stats?.total_earned || 0).toLocaleString()} ATK</div>
                        <p className="stat-subtext">≈ ${( (stats?.total_earned || 0) * 0.05 ).toFixed(2)} USD</p>
                    </div>
                </div>

                <div className="stat-card glass-panel">
                    <div className="stat-icon-wrapper secondary">
                        <Award size={24} />
                    </div>
                    <div className="stat-details">
                        <label>Avg. Daily Yield</label>
                        <div className="stat-value font-mono">{(stats?.avg_reward || 0).toFixed(2)} ATK</div>
                        <p className="stat-subtext">From storage & service proof</p>
                    </div>
                </div>

                <div className="stat-card glass-panel">
                    <div className="stat-icon-wrapper text-muted">
                        <BarChart3 size={24} />
                    </div>
                    <div className="stat-details">
                        <label>Reward Frequency</label>
                        <div className="stat-value font-mono">{(stats?.reward_count || 0)} Triggers</div>
                        <p className="stat-subtext">Successful PoS challenges</p>
                    </div>
                </div>
            </div>

            <div className="history-section glass-panel">
                <div className="section-header">
                    <h3>Recent Reward History</h3>
                    <button 
                        className={`claim-all-btn ${payoutSuccess ? 'success' : ''}`}
                        onClick={handlePayout}
                        disabled={payoutLoading || !stats || stats.total_earned <= 0}
                    >
                        {payoutLoading ? <RefreshCcw size={16} className="animate-spin" /> : 
                         payoutSuccess ? <><CheckCircle2 size={16} /> Payout Success</> : 
                         'Claim All Earnings'}
                    </button>
                </div>
                
                <div className="history-table-wrapper">
                    <table className="history-table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Node ID</th>
                                <th>Reward Type</th>
                                <th>Amount</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {stats?.recent_history.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="text-center py-8 text-muted">No rewards recorded yet. Ensure your nodes are active.</td>
                                </tr>
                            ) : (
                                stats?.recent_history.map((reward, i) => (
                                    <tr key={i}>
                                        <td className="font-mono text-xs">{new Date(reward.timestamp).toLocaleString()}</td>
                                        <td className="font-mono text-xs">{reward.node_id.slice(0, 8)}...</td>
                                        <td>
                                            <span className={`type-tag ${reward.type}`}>
                                                {reward.type === 'storage' ? 'Proof of Storage' : 'Proof of Service'}
                                            </span>
                                        </td>
                                        <td className="font-mono text-success">+{reward.amount} ATK</td>
                                        <td><span className="status-pill completed">Confirmed</span></td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <style>{`
                .stat-card {
                    padding: 1.5rem;
                    display: flex;
                    align-items: center;
                    gap: 1.5rem;
                }
                .stat-card.highlight {
                    border: 1px solid var(--accent-primary);
                    background: linear-gradient(135deg, var(--bg-panel) 0%, rgba(var(--accent-primary-rgb), 0.05) 100%);
                }
                .stat-icon-wrapper {
                    width: 52px;
                    height: 52px;
                    border-radius: 14px;
                    background: rgba(var(--accent-primary-rgb), 0.1);
                    color: var(--accent-primary);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .stat-icon-wrapper.secondary {
                    background: rgba(var(--accent-secondary-rgb), 0.1);
                    color: var(--accent-secondary);
                }
                .stat-details label { display: block; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.25rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.025em; }
                .stat-details .stat-value { font-size: 1.5rem; font-weight: 800; color: var(--text-primary); }
                .history-section { padding: 1.5rem; margin-top: 1rem; }
                .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
                .section-header h3 { font-size: 1.1rem; font-weight: 700; margin: 0; }
                .claim-all-btn { padding: 0.625rem 1.25rem; background: var(--accent-primary); color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
                .claim-all-btn:hover { background: var(--accent-hover); transform: scale(1.02); }
                .history-table { width: 100%; border-collapse: collapse; }
                .history-table th { text-align: left; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color); color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; font-weight: 800; }
                .history-table td { padding: 1rem; border-bottom: 1px solid var(--border-color); font-size: 0.9rem; }
                .type-tag { font-size: 0.75rem; padding: 0.25rem 0.5rem; border-radius: 4px; font-weight: 700; }
                .type-tag.storage { background: rgba(var(--accent-primary-rgb), 0.1); color: var(--accent-primary); }
                .type-tag.service { background: rgba(var(--accent-secondary-rgb), 0.1); color: var(--accent-secondary); }
                .text-success { color: #10b981; }
                .status-pill { font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 800; }
                .status-pill.completed { background: rgba(16, 185, 129, 0.1); color: #10b981; }
            `}</style>
        </div>
    );
};
