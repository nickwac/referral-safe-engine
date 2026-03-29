import React, { useEffect, useState } from 'react';
import { FileSearch, Filter, ShieldCheck } from 'lucide-react';
import { format } from 'date-fns';
import { getAuditLog } from '../api';

const AuditLogPanel = () => {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ action: '', resource_type: '' });

  const loadAudit = async () => {
    setLoading(true);
    try {
      const data = await getAuditLog({ limit: 30, ...filters });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAudit();
  }, [filters.action, filters.resource_type]);

  return (
    <section className="saas-card p-6 space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">Audit Log</h2>
          <p className="text-sm text-zinc-500 mt-1">Immutable admin activity trail for user actions, team changes, org changes, and configuration updates.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="block text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">Action</span>
            <input value={filters.action} onChange={(e) => setFilters((prev) => ({ ...prev, action: e.target.value }))} className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200 outline-none focus:border-zinc-600" placeholder="user.status_changed" />
          </label>
          <label className="text-sm">
            <span className="block text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">Resource</span>
            <input value={filters.resource_type} onChange={(e) => setFilters((prev) => ({ ...prev, resource_type: e.target.value }))} className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200 outline-none focus:border-zinc-600" placeholder="user / organisation" />
          </label>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Entries</p>
          <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-2">{total}</p>
        </div>
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Filtered Action</p>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-2">{filters.action || 'All actions'}</p>
        </div>
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Filtered Resource</p>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-2">{filters.resource_type || 'All resources'}</p>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <div className="grid grid-cols-[1.2fr_0.8fr_0.8fr_0.9fr] gap-4 px-4 py-3 bg-zinc-50 dark:bg-zinc-950/90 text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold">
          <span>Action</span>
          <span>Resource</span>
          <span>Actor</span>
          <span>Timestamp</span>
        </div>
        <div className="max-h-[420px] overflow-auto divide-y divide-zinc-800/60 bg-zinc-50 dark:bg-zinc-950/40">
          {loading ? (
            <div className="p-6 text-sm text-zinc-500">Loading audit entries...</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center text-zinc-500">
              <FileSearch className="w-8 h-8 mx-auto mb-3 text-zinc-700" />
              No audit entries match the current filters.
            </div>
          ) : items.map((item) => (
            <div key={item.id} className="px-4 py-4 grid grid-cols-[1.2fr_0.8fr_0.8fr_0.9fr] gap-4 text-sm hover:bg-white dark:bg-zinc-900/40 transition-colors">
              <div>
                <p className="text-zinc-900 dark:text-zinc-100 font-medium break-words">{item.action}</p>
                {item.after_state && <p className="text-zinc-500 mt-1 text-xs break-words">{JSON.stringify(item.after_state)}</p>}
              </div>
              <div className="text-zinc-700 dark:text-zinc-300">
                <p>{item.resource_type}</p>
                <p className="text-zinc-600 text-xs font-mono mt-1 break-all">{item.resource_id || 'n/a'}</p>
              </div>
              <div className="text-zinc-500 dark:text-zinc-400 font-mono text-xs break-all">{item.actor_id}</div>
              <div className="text-zinc-500 dark:text-zinc-400 text-xs">
                <div className="flex items-center gap-2"><ShieldCheck className="w-3.5 h-3.5 text-zinc-600" />{format(new Date(item.timestamp), 'MMM dd, yyyy')}</div>
                <p className="text-zinc-600 mt-1">{format(new Date(item.timestamp), 'HH:mm:ss')}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default AuditLogPanel;
