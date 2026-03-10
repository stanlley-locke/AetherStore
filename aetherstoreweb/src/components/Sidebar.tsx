import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  MessagesSquare, CircleDollarSign,
  LayoutGrid, Share2, Globe, Trash,
  Settings, ChevronRight, type LucideIcon,
} from 'lucide-react';
import logo from '../assets/cloud-computing.png';
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

const NAV_SECTIONS: NavSection[] = [
  {
    label: 'Storage',
    items: [
      { to: '/drive', exact: true, icon: LayoutGrid, label: 'My Drive' },
      { to: '/drive/shared', icon: Share2, label: 'Public Links', sub: true },
      { to: '/drive/trash', icon: Trash, label: 'Recycle Bin', sub: true },
    ],
  },
  {
    label: 'Social',
    items: [
      { to: '/chat', icon: MessagesSquare, label: 'AetherChat' },
    ],
  },
  {
    label: 'Finance',
    items: [
      { to: '/wallet', icon: CircleDollarSign, label: 'Wallet & Ledger' },
      { to: '/drive/public', icon: Globe, label: 'IPNS Sites', sub: true },
    ],
  },
];

export const Sidebar: React.FC = () => {
  const [isPinned, setIsPinned] = useState(false);

  return (
    <aside className={`sidebar ${isPinned ? 'pinned' : ''}`}>
      {/* Logo / Toggle */}
      <button
        className="sidebar-logo"
        onClick={() => setIsPinned(!isPinned)}
        title={isPinned ? 'Collapse sidebar' : 'Pin sidebar'}
      >
        <div className="logo-icon-wrapper">
          <img src={logo} alt="Logo" className="sidebar-logo-img" />
        </div>
        <span className="sidebar-text brand-name">AetherStore</span>
        <div className="portal-badge">Store</div>
        <ChevronRight size={16} className={`pin-arrow ${isPinned ? 'rotated' : ''}`} />
      </button>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV_SECTIONS.map(section => (
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

      {/* Bottom Settings */}
      <div className="sidebar-bottom">

        <NavLink
          to="/settings"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <Settings size={19} className="nav-icon" />
          <span className="sidebar-text">Settings</span>
        </NavLink>
      </div>
    </aside>
  );
};
