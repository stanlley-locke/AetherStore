import React, { useState, useEffect } from 'react';
import { Globe, Settings, Users, Database, PieChart, RefreshCcw, Save, AlertTriangle, Share2 } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient, type TreasuryStats } from '../../services/api';

export const AdminConsole: React.FC = () => {
    const { did } = useAuthStore();
    const [stats, setStats] = useState<TreasuryStats | null>(null);
    const [params, setParams] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // User Management State
    const [users, setUsers] = useState<any[]>([]);
    const [userSearch, setUserSearch] = useState('');
    const [loadingUsers, setLoadingUsers] = useState(false);

    const loadAdminData = async () => {
        setLoading(true);
        try {
            const client = createAuthenticatedClient(did);
            const [statsRes, paramsRes] = await Promise.all([
                aetherNodeApi.getTreasuryStats(client),
                aetherNodeApi.getParameters(client)
            ]);
            setStats(statsRes.data);
            setParams(paramsRes.data);
            loadUsers(); // Initial users load
        } catch (err) {
            console.error('Failed to load admin data', err);
        } finally {
            setLoading(false);
        }
    };

    const loadUsers = async () => {
        setLoadingUsers(true);
        try {
            const client = createAuthenticatedClient(did);
            const r = await aetherNodeApi.getUsers(client);
            setUsers(r.data.users);
        } catch (err) {
            console.error('Failed to load users', err);
        } finally {
            setLoadingUsers(false);
        }
    };

    const toggleAdminStatus = async (userDid: string, isAdmin: boolean) => {
        if (!confirm(`Are you sure you want to ${isAdmin ? 'elevate' : 'revoke'} admin privileges for ${userDid}?`)) return;
        try {
            const client = createAuthenticatedClient(did);
            await aetherNodeApi.setUserAdminStatus(client, userDid, isAdmin);
            await loadUsers(); // Refresh list
            alert('User permissions updated successfully.');
        } catch (err) {
            alert('Failed to update user permissions.');
        }
    };

    useEffect(() => {
        loadAdminData();
    }, [did]);

    const handleParamChange = (key: string, value: any) => {
        setParams(prev => ({ ...prev, [key]: value }));
    };

    const saveParams = async () => {
        setSaving(true);
        try {
            const client = createAuthenticatedClient(did);
            await aetherNodeApi.updateParameters(client, params);
            alert('Network parameters updated successfully!');
        } catch (err) {
            alert('Failed to update parameters');
        } finally {
            setSaving(false);
        }
    };

    if (loading && !stats) {
        return (
            <div className="loading-state">
                <RefreshCcw className="animate-spin" />
                <p>Establishing secure admin session...</p>
            </div>
        );
    }

    return (
        <div className="admin-console">
            <div className="stats-container">
                <div className="stat-card glass-panel">
                    <div className="stat-icon-wrapper blue">
                        <PieChart size={24} />
                    </div>
                    <div className="stat-details">
                        <label>Circulating Supply</label>
                        <div className="stat-value font-mono">{(stats?.atk_circulating_supply || 0).toLocaleString()} ATK</div>
                        <p className="stat-subtext">Total liquidity across wallets</p>
                    </div>
                </div>

                <div className="stat-card glass-panel">
                    <div className="stat-icon-wrapper blue">
                        <Database size={24} />
                    </div>
                    <div className="stat-details">
                        <label>Global Storage</label>
                        <div className="stat-value font-mono">{( (stats?.global_storage_consumption_bytes || 0) / 1024 / 1024 / 1024 ).toFixed(2)} GB</div>
                        <p className="stat-subtext">Across {stats?.total_active_objects || 0} active objects</p>
                    </div>
                </div>

                <div className="stat-card glass-panel">
                    <div className="stat-icon-wrapper blue">
                        <Globe size={24} />
                    </div>
                    <div className="stat-details">
                        <label>Network Health</label>
                        <div className="stat-value font-mono">{stats?.active_network_nodes || 0} Nodes</div>
                        <p className="stat-subtext">Active Kademlia peers online</p>
                    </div>
                </div>
            </div>

            <div className="admin-grid">
                <div className="admin-section glass-panel">
                    <div className="section-header">
                        <div className="flex-align-center gap-2">
                            <Settings size={18} />
                            <h3>Network Parameter Controls (God-Mode)</h3>
                        </div>
                        <button 
                            className="save-btn" 
                            onClick={saveParams}
                            disabled={saving}
                        >
                            <Save size={16} />
                            {saving ? 'Saving...' : 'Apply Changes'}
                        </button>
                    </div>

                    <div className="params-list">
                        <div className="param-item">
                            <div className="param-info">
                                <label>Shard Replication Factor</label>
                                <p>Minimum copies per shard across different nodes (Erasure Coding).</p>
                            </div>
                            <input 
                                type="number" 
                                value={params.replication_factor || 3}
                                onChange={(e) => handleParamChange('replication_factor', parseInt(e.target.value))}
                                className="param-input"
                            />
                        </div>

                        <div className="param-item">
                            <div className="param-info">
                                <label>Daily Block Reward (ATK)</label>
                                <p>Total tokens minted per day for mining rewards.</p>
                            </div>
                            <input 
                                type="number" 
                                value={params.daily_reward_emission || 1000}
                                onChange={(e) => handleParamChange('daily_reward_emission', parseInt(e.target.value))}
                                className="param-input"
                            />
                        </div>

                        <div className="param-item">
                            <div className="param-info">
                                <label>Base Storage Cost (ATK/GB/Day)</label>
                                <p>Foundational price of storage on the network.</p>
                            </div>
                            <input 
                                type="number" 
                                step="0.01"
                                value={params.storage_cost_per_gb || 0.1}
                                onChange={(e) => handleParamChange('storage_cost_per_gb', parseFloat(e.target.value))}
                                className="param-input"
                            />
                        </div>
                    </div>
                </div>

                <div className="admin-section glass-panel">
                    <div className="section-header">
                        <div className="flex-align-center gap-2">
                            <Users size={18} />
                            <h3>User Management & Privileges</h3>
                        </div>
                    </div>
                    
                    <div className="search-box">
                        <input 
                            type="text" 
                            placeholder="Search by DID (did:aether:ath1...)" 
                            className="search-input"
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                        />
                        <button className="search-btn" onClick={loadUsers}>
                            <RefreshCcw size={14} className={loadingUsers ? 'animate-spin' : ''} />
                        </button>
                    </div>

                    <div className="user-list-container">
                        {loadingUsers ? (
                            <div className="mini-loading">Querying network identities...</div>
                        ) : (
                            <table className="admin-table">
                                <thead>
                                    <tr>
                                        <th>Identity (DID)</th>
                                        <th>Role</th>
                                        <th style={{ textAlign: 'right' }}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.filter(u => !userSearch || u.did.includes(userSearch)).map(user => (
                                        <tr key={user.did}>
                                            <td className="font-mono" style={{ fontSize: '0.75rem' }}>{user.did?.slice(0, 15)}...</td>
                                            <td>
                                                <span className={`role-badge ${user.is_network_admin ? 'admin' : 'user'}`}>
                                                    {user.is_network_admin ? 'Network Admin' : 'Standard User'}
                                                </span>
                                            </td>
                                            <td style={{ textAlign: 'right' }}>
                                                <button 
                                                    className={`action-link ${user.is_network_admin ? 'revoke' : 'promote'}`}
                                                    onClick={() => toggleAdminStatus(user.did, !user.is_network_admin)}
                                                >
                                                    {user.is_network_admin ? 'Revoke Admin' : 'Elevate to Admin'}
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>

                    <div className="moderation-alert" style={{ marginTop: '1.5rem' }}>
                        <AlertTriangle size={18} className="text-blue" />
                        <p>Elevation grants full control over network parameters and treasury functions.</p>
                    </div>
                </div>

                {/* Network Topology Graph */}
                <div className="admin-section glass-panel topology-section">
                    <div className="section-header">
                        <div className="flex-align-center gap-2">
                            <Share2 size={18} />
                            <h3>Global Network Topology (DHT)</h3>
                        </div>
                    </div>
                    
                    <div className="topology-viewport">
                        <div className="topology-grid"></div>
                        {Array.from({ length: stats?.active_network_nodes || 12 }).map((_, i) => {
                            const x = (i * 27) % 100;
                            const y = (i * 13) % 100;
                            const isActive = i < (stats?.active_network_nodes || 8);
                            return (
                                <div 
                                    key={i} 
                                    className={`node-dot ${isActive ? 'active' : 'inactive'}`}
                                    style={{ left: `${x}%`, top: `${y}%` }}
                                >
                                    <div className="node-tooltip font-mono">
                                        node-{i+1} <br/>
                                        lat: {x.toFixed(2)} <br/>
                                        lon: {y.toFixed(2)}
                                    </div>
                                </div>
                            );
                        })}
                        {/* Connecting lines simulation */}
                        <svg className="topology-lines">
                            <circle cx="50%" cy="50%" r="2" fill="var(--accent-primary)" />
                        </svg>
                    </div>

                    <div className="topology-legend">
                        <div className="legend-item"><span className="dot active"></span> Active Node</div>
                        <div className="legend-item"><span className="dot inactive"></span> Peer/Bucket</div>
                        <div className="legend-item"><span className="line"></span> DHT Connection</div>
                    </div>
                </div>
            </div>

            <style>{`
                .stat-icon-wrapper.blue { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
                .stat-icon-wrapper.green { background: rgba(16, 185, 129, 0.1); color: #10b981; }
                .admin-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1rem; }
                .admin-section { padding: 1.5rem; }
                .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
                .save-btn { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; background: var(--accent-primary); color: #fff; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; }
                .params-list { display: flex; flex-direction: column; gap: 1.5rem; }
                .param-item { display: flex; justify-content: space-between; align-items: flex-start; gap: 2rem; }
                .param-info label { display: block; font-weight: 700; font-size: 0.95rem; margin-bottom: 0.25rem; }
                .param-info p { font-size: 0.85rem; color: var(--text-muted); margin: 0; }
                .param-input { width: 100px; padding: 0.5rem; background: var(--bg-hover); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 6px; font-family: var(--font-mono); font-weight: 600; text-align: center; }
                .search-box { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
                .search-input { flex: 1; padding: 0.75rem; background: var(--bg-hover); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 8px; font-size: 0.875rem; outline: none; transition: border-color 0.2s; }
                .search-input:focus { border-color: var(--accent-primary); }
                .search-btn { padding: 0.75rem; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; width: 46px; }
                
                .user-list-container { min-height: 200px; }
                .mini-loading { color: var(--text-muted); font-size: 0.875rem; text-align: center; padding: 2rem; }
                .admin-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
                .admin-table th { text-align: left; padding: 0.75rem 0.5rem; border-bottom: 1px solid var(--border-color); color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.05em; }
                .admin-table td { padding: 1rem 0.5rem; border-bottom: 1px solid var(--border-color); vertical-align: middle; }
                
                .role-badge { padding: 0.2rem 0.6rem; borderRadius: 4px; font-size: 0.7rem; font-weight: 700; border-radius: 4px; }
                .role-badge.admin { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
                .role-badge.user { background: var(--bg-hover); color: var(--text-muted); }
                
                .action-link { background: none; border: none; font-size: 0.75rem; font-weight: 600; cursor: pointer; padding: 0; }
                .action-link.promote { color: var(--accent-primary); }
                .action-link.revoke { color: #ef4444; }
                .action-link:hover { text-decoration: underline; }

                .moderation-alert { display: flex; align-items: center; gap: 0.75rem; padding: 1rem; background: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 8px; color: var(--text-secondary); font-size: 0.85rem; }
                .flex-align-center { display: flex; align-items: center; }
                .gap-2 { gap: 0.5rem; }
                .text-blue { color: #3b82f6; }

                /* Topology Graph Styles */
                .topology-section { grid-column: span 2; }
                .topology-viewport {
                    height: 350px;
                    background: #020617; /* Very dark background */
                    border-radius: 12px;
                    position: relative;
                    overflow: hidden;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    margin-bottom: 1rem;
                }
                .topology-grid {
                    position: absolute;
                    inset: 0;
                    background-image: 
                        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
                    background-size: 40px 40px;
                }
                .node-dot {
                    position: absolute;
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    transform: translate(-50%, -50%);
                    cursor: pointer;
                    z-index: 10;
                    transition: all 0.3s;
                }
                .node-dot.active { background: #10b981; box-shadow: 0 0 10px #10b981; }
                .node-dot.inactive { background: #475569; }
                .node-dot:hover { transform: translate(-50%, -50%) scale(1.5); z-index: 20; }
                .node-tooltip {
                    position: absolute;
                    top: 100%; left: 50%;
                    transform: translateX(-50%);
                    background: #1e293b;
                    color: #fff;
                    padding: 0.5rem;
                    border-radius: 4px;
                    font-size: 0.7rem;
                    white-space: nowrap;
                    opacity: 0;
                    visibility: hidden;
                    pointer-events: none;
                    transition: all 0.2s;
                    margin-top: 0.5rem;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5);
                }
                .node-dot:hover .node-tooltip { opacity: 1; visibility: visible; }
                .topology-lines { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
                .topology-legend { display: flex; gap: 2rem; justify-content: center; }
                .legend-item { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--text-muted); font-weight: 600; }
                .legend-item .dot { width: 8px; height: 8px; border-radius: 50%; }
                .legend-item .dot.active { background: #10b981; }
                .legend-item .dot.inactive { background: #475569; }
                .legend-item .line { width: 20px; height: 1px; background: rgba(255,255,255,0.2); }
            `}</style>
        </div>
    );
};
