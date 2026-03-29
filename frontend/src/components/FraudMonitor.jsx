import React, { useEffect, useState } from 'react';
import { getFraudFlags } from '../api';
import { ShieldAlert, AlertTriangle, Repeat, UserX, Copy, ExternalLink } from 'lucide-react';
import { format } from 'date-fns';
import toast from 'react-hot-toast';

const truncateId = (value) => (value ? `${value.substring(0, 8)}...` : 'Unknown');

const ReasonBadge = ({ reason }) => {
  let config = { bg: 'bg-zinc-500/10', text: 'text-zinc-500 dark:text-zinc-400', border: 'border-zinc-500/20', icon: AlertTriangle, label: 'Unknown' };

  if (reason === 'cycle') {
    config = { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', icon: Repeat, label: 'Cycle Blocked' };
  } else if (reason === 'self_referral') {
    config = { bg: 'bg-amber-500/10', text: 'text-amber-500', border: 'border-amber-500/20', icon: UserX, label: 'Self Referral' };
  } else if (reason === 'velocity') {
    config = { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/20', icon: ShieldAlert, label: 'Velocity Limit' };
  } else if (reason === 'duplicate') {
    config = { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/20', icon: Copy, label: 'Duplicate Claim' };
  }

  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-medium tracking-wide uppercase ${config.bg} ${config.text} border ${config.border}`}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
};

const FraudMonitor = ({ onSelectUser }) => {
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFlags = async () => {
      try {
        const data = await getFraudFlags();
        setFlags(data.items || []);
        setLoading(false);
      } catch (error) {
        console.error('Failed to fetch fraud flags:', error);
      }
    };

    fetchFlags();
    const interval = setInterval(fetchFlags, 10000);
    return () => clearInterval(interval);
  }, []);

  const copyUserId = async (userId) => {
    if (!userId) return;
    await navigator.clipboard.writeText(userId);
    toast.success('User UUID copied');
  };

  const openInExplorer = (userId) => {
    if (!userId) return;
    onSelectUser?.(userId, 'Fraud Monitor');
    toast.success('Loaded in DAG Explorer');
  };

  return (
    <div className="saas-card flex flex-col h-[400px] overflow-hidden">
      <div className="p-6 border-b border-zinc-200 dark:border-zinc-800/60 bg-zinc-50 dark:bg-zinc-950/50 flex items-center gap-3">
        <div className="w-8 h-8 rounded border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-center">
          <ShieldAlert className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">Fraud Monitor</h2>
          <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-widest mt-0.5">Real-Time Alerts</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="animate-pulse flex flex-col p-4 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 bg-zinc-100 dark:bg-zinc-800/50 rounded"></div>
            ))}
          </div>
        ) : flags.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-zinc-500">
             <ShieldAlert className="w-10 h-10 mb-3 text-zinc-700" />
             <p className="text-sm font-medium">No fraud detected yet. You are safe.</p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse text-sm">
            <thead className="sticky top-0 bg-zinc-50 dark:bg-zinc-950/95 backdrop-blur z-10 border-b border-zinc-200 dark:border-zinc-800 text-[11px] uppercase tracking-wider text-zinc-500 font-semibold">
              <tr>
                <th className="py-3 px-6 font-medium">User ID</th>
                <th className="py-3 px-6 font-medium">Timestamp</th>
                <th className="py-3 px-6 font-medium text-right">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {flags.map((flag, idx) => (
                <tr key={flag.id} className={`${idx % 2 === 0 ? 'bg-white dark:bg-zinc-900/20' : 'bg-transparent'} hover:bg-zinc-100 dark:bg-zinc-800/30 transition-colors`}>
                  <td className="py-3 px-6 text-zinc-700 dark:text-zinc-300 font-mono text-[13px] tracking-tight">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        title={flag.user_id || 'Unknown'}
                        onClick={() => openInExplorer(flag.user_id)}
                        className="text-left hover:text-zinc-900 dark:text-zinc-100 transition-colors"
                      >
                        {truncateId(flag.user_id)}
                      </button>
                      <button type="button" title="Copy full UUID" onClick={() => copyUserId(flag.user_id)} className="text-zinc-500 hover:text-zinc-800 dark:text-zinc-200 transition-colors">
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                      <button type="button" title="Open in DAG explorer" onClick={() => openInExplorer(flag.user_id)} className="text-zinc-500 hover:text-zinc-800 dark:text-zinc-200 transition-colors">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                  <td className="py-3 px-6 text-zinc-500 dark:text-zinc-400 font-tabular-nums text-sm">
                    {format(new Date(flag.timestamp), 'MMM dd, HH:mm:ss')}
                  </td>
                  <td className="py-3 px-6 text-right">
                    <ReasonBadge reason={flag.reason} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default FraudMonitor;
