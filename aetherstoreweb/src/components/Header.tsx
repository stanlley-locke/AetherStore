import React from 'react';
import { Search, Bell, Sun, Moon, LogOut, Shield, Database } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { useAuthStore } from '../store/useAuthStore';
import './Layout.css';

export const Header: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuthStore();
  const location = useLocation();

  const isNodePortal = location.pathname.startsWith('/aethernode');

  return (
    <header className="header">
      <div className="header-left">
        <div className="header-search">
            <Search size={18} color="var(--text-muted)" />
            <input type="text" placeholder={isNodePortal ? "Search nodes, logs, metrics..." : "Search files, chats, transactions..."} />
        </div>
        
        <div className={`portal-indicator ${isNodePortal ? 'node' : 'store'}`}>
            {isNodePortal ? <Shield size={14} /> : <Database size={14} />}
            <span>{isNodePortal ? 'AetherNode Operator' : 'AetherStore Client'}</span>
        </div>
      </div>

      <div className="header-actions">
        <button className="icon-button" onClick={toggleTheme} title="Toggle Theme">
          {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
        </button>
        <button className="icon-button" title="Notifications">
          <Bell size={20} />
        </button>
        <button className="icon-button" title="Logout" onClick={logout}>
          <LogOut size={20} />
        </button>
      </div>
    </header>
  );
};
