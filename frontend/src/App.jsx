import React, { useEffect, useState } from 'react';
import { Toaster } from 'react-hot-toast';
import { Hexagon, LogOut, Sun, Moon } from 'lucide-react';
import MetricsPanel from './components/MetricsPanel';
import FraudMonitor from './components/FraudMonitor';
import ActivityFeed from './components/ActivityFeed';
import GraphView from './components/GraphView';
import LoginPage from './components/LoginPage';
import UserProfilePanel from './components/UserProfilePanel';
import AuditLogPanel from './components/AuditLogPanel';
import SessionPanel from './components/SessionPanel';
import { getCurrentAdmin, getSavedAdminSession, logoutAdmin } from './api';

const adminTabs = [
  { id: 'profile', label: 'User Profile' },
  { id: 'audit', label: 'Audit Log' },
  { id: 'sessions', label: 'Sessions' },
];

function App() {
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectionSource, setSelectionSource] = useState('');
  const [admin, setAdmin] = useState(getSavedAdminSession());
  const [booting, setBooting] = useState(Boolean(getSavedAdminSession()));
  const [activeTab, setActiveTab] = useState('profile');
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    if (theme === 'dark') { document.documentElement.classList.add('dark'); } else { document.documentElement.classList.remove('dark'); }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const handleSelectUser = (userId, source) => {
    setSelectedUserId(userId);
    setSelectionSource(source);
    setActiveTab('profile');
  };

  useEffect(() => {
    const bootstrap = async () => {
      if (!admin) {
        setBooting(false);
        return;
      }
      try {
        const current = await getCurrentAdmin();
        setAdmin(current);
      } catch {
        setAdmin(null);
      } finally {
        setBooting(false);
      }
    };
    bootstrap();
  }, []);

  const handleLogout = async () => {
    await logoutAdmin();
    setAdmin(null);
    setSelectedUserId('');
    setSelectionSource('');
  };

  if (booting) {
    return <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950" />;
  }

  return (
    <div className="min-h-screen font-sans selection:bg-cyan-500/30 selection:text-cyan-100 bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#18181b',
            color: '#f4f4f5',
            border: '1px solid #27272a',
            fontSize: '14px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)',
          },
        }}
      />

      {!admin ? (
        <LoginPage onAuthenticated={setAdmin} />
      ) : (
        <>
          <header className="saas-header sticky top-0 z-50 px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded border border-zinc-200 dark:border-zinc-800 flex items-center justify-center bg-white dark:bg-zinc-900 shadow-sm shadow-black/50">
                <Hexagon className="w-4 h-4 text-zinc-700 dark:text-zinc-300" />
              </div>
              <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
                <h1 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">Referral safe engine</h1>
                <span className="hidden sm:inline text-zinc-600 text-sm">/</span>
                <span className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">{admin.org_name || 'Global Admin'} � {admin.role.replaceAll('_', ' ')}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-4 md:gap-6">
              <div className="hidden md:flex items-center gap-2 group cursor-default border-r border-zinc-200 dark:border-zinc-800 dark:border-zinc-800 pr-6">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-40"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></span>
                </span>
                <span className="text-emerald-500/90 text-xs font-semibold tracking-wider uppercase transition-colors">Authenticated</span>
              </div>
              <div className="flex items-center gap-3">
                <button onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} className="w-9 h-9 flex items-center justify-center rounded-full border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors" title="Toggle Theme">
                  {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                </button>
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-sm font-medium text-zinc-900 dark:text-zinc-200">{admin.email}</span>
                  <span className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">JWT scoped</span>
                </div>
                <button onClick={handleLogout} className="w-9 h-9 rounded-full border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 flex items-center justify-center text-zinc-600 dark:text-zinc-300 hover:text-rose-600 dark:hover:text-rose-400 hover:border-rose-200 dark:hover:border-rose-900 transition-colors" title="Sign out">
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </header>

          <main className="max-w-[1600px] mx-auto p-6 space-y-6">
            <section>
              <MetricsPanel />
            </section>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <GraphView selectedUserId={selectedUserId} selectionSource={selectionSource} />
              </div>

              <div className="space-y-6 flex flex-col">
                <FraudMonitor onSelectUser={handleSelectUser} />
                <ActivityFeed onSelectUser={handleSelectUser} />
              </div>
            </div>

            <section className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {adminTabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`px-4 py-2 rounded-full text-sm border transition-colors ${activeTab === tab.id ? 'bg-cyan-500 text-zinc-950 border-cyan-400' : 'bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-800 hover:border-zinc-600'}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {activeTab === 'profile' && <UserProfilePanel selectedUserId={selectedUserId} onSelectUser={handleSelectUser} />}
              {activeTab === 'audit' && <AuditLogPanel />}
              {activeTab === 'sessions' && <SessionPanel onLoggedOut={() => setAdmin(null)} />}
            </section>
          </main>
        </>
      )}
    </div>
  );
}

export default App;
