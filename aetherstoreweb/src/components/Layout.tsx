import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ChevronRight } from 'lucide-react';
import './Layout.css';

export const Layout: React.FC = () => {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter((x) => x);

  // Dynamic Breadcrumbs
  const breadcrumbs = (
    <div className="breadcrumb">
      <span>Home</span>
      {pathnames.map((value, index) => {
        const isLast = index === pathnames.length - 1;
        // Capitalize the first letter
        const title = value.charAt(0).toUpperCase() + value.slice(1);
        
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
      <Sidebar />
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
