import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { NodeSidebar } from './NodeSidebar';
import { Header } from './Header';
import { ChevronRight } from 'lucide-react';
import './Layout.css';

export const NodeLayout: React.FC = () => {
    const location = useLocation();
    const pathnames = location.pathname.split('/').filter((x) => x);

    const breadcrumbs = (
        <div className="breadcrumb">
            <span style={{ color: 'var(--accent-primary)' }}>AetherNode</span>
            {pathnames.map((value, index) => {
                const isLast = index === pathnames.length - 1;
                const title = value.charAt(0).toUpperCase() + value.slice(1);
                if (value === 'aethernode') return null;
                return (
                    <React.Fragment key={value}>
                        <ChevronRight size={14} />
                        {isLast ? <span>{title}</span> : <a href={`/${value}`}>{title}</a>}
                    </React.Fragment>
                );
            })}
        </div>
    );

    return (
        <div className="layout-container">
            <NodeSidebar />
            <div className="main-content">
                <Header />
                <main className="page-body">
                    {breadcrumbs}
                    <Outlet />
                </main>
            </div>
        </div>
    );
};
