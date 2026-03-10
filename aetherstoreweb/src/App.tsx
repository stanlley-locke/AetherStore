import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Layout } from './components/Layout';
import { NodeLayout } from './components/NodeLayout';
import { Dashboard } from './pages/Dashboard';
import { Drive } from './pages/Drive';
import { Chat } from './pages/Chat';
import { Wallet } from './pages/Wallet';
import { Trash } from './pages/Trash';
import { SharedWorkspaces } from './pages/SharedWorkspaces';
import { IpnsSites } from './pages/IpnsSites';
import { Login } from './pages/Login';
import { AetherNodeLogin } from './pages/AetherNodeLogin';
import { SharePage } from './pages/SharePage';
import { AetherNode } from './pages/AetherNode';
import { ThemeProvider } from './context/ThemeContext';
import { useAuthStore } from './store/useAuthStore';

// ── AetherStore portal guard ──────────────────────────────
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
};

// ── AetherNode portal guard (redirects to its own login) ──
const NodeProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/aethernode/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
};

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* ── Public Routes ───────────────────────────── */}
          <Route path="/login" element={<Login />} />
          <Route path="/share/:token" element={<SharePage />} />
          <Route path="/aethernode/login" element={<AetherNodeLogin />} />

          {/* ── AetherStore Portal ──────────────────────── */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/drive" replace />} />
            <Route path="drive" element={<Drive />} />
            <Route path="drive/trash" element={<Trash />} />
            <Route path="drive/shared" element={<SharedWorkspaces />} />
            <Route path="drive/public" element={<IpnsSites />} />
            <Route path="chat" element={<Chat />} />
            <Route path="wallet" element={<Wallet />} />
            <Route path="settings" element={<Dashboard />} />
          </Route>

          {/* ── AetherNode Portal (separate layout + login) */}
          <Route
            path="/aethernode"
            element={
              <NodeProtectedRoute>
                <NodeLayout />
              </NodeProtectedRoute>
            }
          >
            <Route index element={<AetherNode />} />
            <Route path="manage" element={<AetherNode />} />
            <Route path="rewards" element={<AetherNode />} />
            <Route path="payouts" element={<AetherNode />} />
            <Route path="health" element={<AetherNode />} />
            <Route path="console" element={<AetherNode />} />
            <Route path="admin" element={<AetherNode />} />
            <Route path="*" element={<AetherNode />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
