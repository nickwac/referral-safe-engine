import React, { useEffect, useState } from 'react';
import { LaptopMinimal, Lock, ShieldOff } from 'lucide-react';
import { formatDistanceToNowStrict, format } from 'date-fns';
import toast from 'react-hot-toast';
import { getSessions, logoutAdmin, revokeOtherSessions, revokeSession } from '../api';

const SessionPanel = ({ onLoggedOut }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');

  const loadSessions = async () => {
    setLoading(true);
    try {
      const data = await getSessions();
      setSessions(data.items || []);
    } catch (error) {
      console.error(error);
      toast.error('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleRevoke = async (sessionId, isCurrent) => {
    setBusyId(sessionId);
    try {
      await revokeSession(sessionId);
      if (isCurrent) {
        await logoutAdmin();
        onLoggedOut?.();
        return;
      }
      toast.success('Session revoked');
      await loadSessions();
    } catch (error) {
      console.error(error);
      toast.error('Failed to revoke session');
    } finally {
      setBusyId('');
    }
  };

  const handleRevokeOthers = async () => {
    setBusyId('others');
    try {
      const data = await revokeOtherSessions();
      toast.success(`Revoked ${data.revoked} other sessions`);
      await loadSessions();
    } catch (error) {
      console.error(error);
      toast.error('Failed to revoke other sessions');
    } finally {
      setBusyId('');
    }
  };

  return (
    <section className="saas-card p-6 space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">Session Management</h2>
          <p className="text-sm text-zinc-500 mt-1">Review your active refresh sessions, revoke old devices, and keep only the current browser trusted.</p>
        </div>
        <button type="button" onClick={handleRevokeOthers} disabled={busyId === 'others'} className="rounded-lg border border-red-900/40 bg-red-950/20 px-4 py-2 text-sm text-red-300 hover:bg-red-950/30 transition-colors disabled:opacity-60">
          {busyId === 'others' ? 'Revoking...' : 'Revoke Other Sessions'}
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Total Sessions</p>
          <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-2">{sessions.length}</p>
        </div>
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Current Session</p>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-2">{sessions.find((item) => item.is_current)?.device_hint || 'Unknown device'}</p>
        </div>
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Revoked</p>
          <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-2">{sessions.filter((item) => item.revoked).length}</p>
        </div>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="p-6 text-sm text-zinc-500">Loading sessions...</div>
        ) : sessions.map((session) => (
          <div key={session.id} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="flex items-start gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-center flex-shrink-0">
                <LaptopMinimal className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-zinc-900 dark:text-zinc-100 font-medium break-words">{session.device_hint || 'Unknown device'}</p>
                  {session.is_current && <span className="px-2 py-0.5 rounded-full text-[10px] uppercase tracking-[0.18em] bg-cyan-500/10 border border-cyan-500/20 text-cyan-300">Current</span>}
                  {session.revoked && <span className="px-2 py-0.5 rounded-full text-[10px] uppercase tracking-[0.18em] bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400">Revoked</span>}
                </div>
                <p className="text-sm text-zinc-500 mt-1">IP {session.ip_address || 'unknown'} � last active {formatDistanceToNowStrict(new Date(session.last_active_at), { addSuffix: true })}</p>
                <p className="text-xs text-zinc-600 mt-1">Expires {format(new Date(session.expires_at), 'MMM dd, yyyy HH:mm')}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => handleRevoke(session.id, session.is_current)} disabled={session.revoked || busyId === session.id} className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200 hover:border-zinc-600 transition-colors disabled:opacity-50">
                {busyId === session.id ? 'Revoking...' : session.is_current ? 'Sign Out Here' : 'Revoke'}
              </button>
              <div className="w-9 h-9 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-center text-zinc-500">
                {session.revoked ? <ShieldOff className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default SessionPanel;
