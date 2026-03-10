import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, BarChart3, Shield,
  Server, Database, HeartPulse, Terminal, Banknote
} from 'lucide-react';
import { FleetOverview } from '../components/AetherNode/FleetOverview';
import { NodeManagement } from '../components/AetherNode/NodeManagement';
import { MiningRewards } from '../components/AetherNode/MiningRewards';
import { PayoutHistory } from '../components/AetherNode/PayoutHistory';
import { NodeHealth } from '../components/AetherNode/NodeHealth';
import { NetworkConsole } from '../components/AetherNode/NetworkConsole';
import { AdminConsole } from '../components/AetherNode/AdminConsole';
import { aetherNodeApi, createAuthenticatedClient } from '../services/api';
import { useAuthStore } from '../store/useAuthStore';
import './AetherNode.css';

type TabId = 'fleet' | 'manage' | 'rewards' | 'payouts' | 'health' | 'console' | 'admin';

export const AetherNode: React.FC = () => {
    const { did } = useAuthStore();
    const location = useLocation();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<TabId>('fleet');
    const [isAdmin, setIsAdmin] = useState(false);

    useEffect(() => {
        const checkAdmin = async () => {
            if (!did) return;
            try {
                const client = createAuthenticatedClient(did);
                const r = await aetherNodeApi.getAdminStatus(client);
                setIsAdmin(r.data.is_network_admin);
            } catch (e) {
                console.error("Failed to check admin status", e);
            }
        };
        checkAdmin();
    }, [did]);

    useEffect(() => {
        const path = location.pathname;
        if (path.includes('rewards')) setActiveTab('rewards');
        else if (path.includes('payouts')) setActiveTab('payouts');
        else if (path.includes('manage')) setActiveTab('manage');
        else if (path.includes('health')) setActiveTab('health');
        else if (path.includes('console')) setActiveTab('console');
        else if (path.includes('admin')) setActiveTab('admin');
        else setActiveTab('fleet');
    }, [location.pathname]);

    const tabs: { id: TabId; label: string; icon: any; adminOnly?: boolean }[] = [
        { id: 'fleet', label: 'Fleet Overview', icon: Server },
        { id: 'manage', label: 'Node Management', icon: Database },
        { id: 'rewards', label: 'Mining Rewards', icon: BarChart3 },
        { id: 'payouts', label: 'Payout History', icon: Banknote },
        { id: 'health', label: 'Node Health', icon: HeartPulse },
        { id: 'console', label: 'Terminal Console', icon: Terminal },
        { id: 'admin', label: 'Network Control', icon: Shield, adminOnly: true },
    ];

    const renderContent = () => {
        switch (activeTab) {
            case 'fleet': return <FleetOverview />;
            case 'manage': return <NodeManagement />;
            case 'rewards': return <MiningRewards />;
            case 'payouts': return <PayoutHistory />;
            case 'health': return <NodeHealth />;
            case 'console': return <NetworkConsole />;
            case 'admin': return <AdminConsole />;
            default: return <FleetOverview />;
        }
    };

    const handleTabClick = (id: TabId) => {
        const path = id === 'fleet' ? '/aethernode' : `/aethernode/${id}`;
        navigate(path);
    };

    return (
        <div className="aethernode-container">
            <header className="aethernode-header">
                <div className="header-title">
                    <Activity size={32} className="header-icon" />
                    <div>
                        <h1>AetherNode Portal</h1>
                        <p className="subtitle">Infrastructure Orchestration & Global P2P Network</p>
                    </div>
                </div>
            </header>

            <nav className="aethernode-tabs">
                {tabs.map(tab => (
                    (!tab.adminOnly || isAdmin) && (
                        <button 
                            key={tab.id}
                            className={`nav-tab ${activeTab === tab.id ? 'active' : ''} ${tab.adminOnly ? 'admin-tab' : ''}`}
                            onClick={() => handleTabClick(tab.id)}
                        >
                            <tab.icon size={16} />
                            {tab.label}
                        </button>
                    )
                ))}
            </nav>

            <main className="aethernode-content">
                {renderContent()}
            </main>
        </div>
    );
};
