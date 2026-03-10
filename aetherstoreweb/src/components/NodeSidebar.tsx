import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Activity, BarChart3, Shield,
  ChevronRight, type LucideIcon,
  Database, Cpu, HeartPulse, LogOut
} from 'lucide-react';
import logo from '../assets/cloud-computing.png';
import { useAuthStore } from '../store/useAuthStore';
import './Sidebar.css';

interface NavSection {
  label: string;
  items: Array<{
    to: string;
    label: string;
    icon: LucideIcon;
    exact?: boolean;
    sub?: boolean;
  }>;
}

const NODE_NAV_SECTIONS: NavSection[] = [
  {
    label: 'Orchestration',
    items: [
      { to: '/aethernode', exact: true, icon: Activity, label: 'Fleet Overview' },
      { to: '/aethernode/nodes', icon: Cpu, label: 'Node Management', sub: true },
    ],
  },
  {
    label: 'Economics',
    items: [
      { to: '/aethernode/earnings', icon: BarChart3, label: 'Mining Rewards' },
      { to: '/aethernode/payouts', icon: Database, label: 'Payout History', sub: true },
    ],
  },
  {
    label: 'Network',
    items: [
      { to: '/aethernode/admin', icon: Shield, label: 'Admin Console' },
      { to: '/aethernode/health', icon: HeartPulse, label: 'Global Health', sub: true },
    ],
  },
];

export const NodeSidebar: React.FC = () => {
  const [isPinned, setIsPinned] = useState(false);
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/aethernode/login');
  };

  return (
    <aside className={`sidebar ${isPinned ? 'pinned' : ''}`}>
      {/* Logo / Toggle */}
      <button
        className="sidebar-logo"
        onClick={() => setIsPinned(!isPinned)}
      >
        <div className="logo-icon-wrapper">
          <img src={logo} alt="Logo" className="sidebar-logo-img" />
        </div>
        <span className="sidebar-text brand-name">AetherNode</span>
        <div className="portal-badge">Node</div>
        <ChevronRight size={16} className={`pin-arrow ${isPinned ? 'rotated' : ''}`} />
      </button>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NODE_NAV_SECTIONS.map(section => (
          <div key={section.label} className="nav-section">
            <p className="nav-section-label sidebar-text">{section.label}</p>
            {section.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                className={({ isActive }) =>
                  `nav-item ${item.sub ? 'nav-sub' : ''} ${isActive ? 'active' : ''}`
                }
              >
                <item.icon size={item.sub ? 17 : 19} className="nav-icon" />
                <span className="sidebar-text">{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Bottom Section */}
      <div className="sidebar-bottom">

        <button
          onClick={handleLogout}
          className="nav-item"
          style={{ width: '100%', textAlign: 'left', cursor: 'pointer', background: 'none', border: 'none', color: 'var(--text-muted)' }}
        >
          <LogOut size={19} className="nav-icon" />
          <span className="sidebar-text">Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
