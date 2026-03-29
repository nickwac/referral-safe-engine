import React, { useEffect, useState } from 'react';
import { getMetrics, seedRewardConfig } from '../api';
import { Users, TrendingUp, AlertTriangle, CheckCircle, XCircle, DollarSign, Info, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

const MetricCard = ({ title, value, icon: Icon, isCurrency = false, accent = false }) => (
  <div className="saas-card flex flex-col justify-between p-5 transition-colors hover:bg-white dark:bg-zinc-900/50 group">
    <div className="flex items-start justify-between mb-4">
      <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium tracking-wide uppercase">{title}</p>
      <div className={`w-8 h-8 rounded border ${accent ? 'border-indigo-500/30 bg-indigo-500/10' : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/50'} flex items-center justify-center transition-colors group-hover:border-zinc-300 dark:border-zinc-700`}>
        <Icon className={`w-4 h-4 ${accent ? 'text-indigo-400' : 'text-zinc-500 dark:text-zinc-400 group-hover:text-zinc-700 dark:text-zinc-300'}`} />
      </div>
    </div>
    <div>
      <h3 className={`text-2xl font-semibold text-zinc-900 dark:text-zinc-100 ${isCurrency ? 'font-mono tracking-tight' : ''}`}>
        {value}
      </h3>
    </div>
  </div>
);

const MetricsPanel = () => {
  const [metrics, setMetrics] = useState({
    total_users: 0,
    total_referrals: 0,
    total_rewards_distributed: 0,
    total_fraud_flags: 0,
    accepted_claims: 0,
    rejected_claims: 0
  });
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const fetchMetrics = async () => {
    try {
      const data = await getMetrics();
      setMetrics(data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
      if (loading) toast.error('Failed to connect to backend.', { id: 'metrics-err' });
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSeedConfig = async () => {
    setSeeding(true);
    try {
      await seedRewardConfig();
      toast.success('Reward config seeded and backfilled.');
      await fetchMetrics();
    } catch (e) {
      console.error(e);
      toast.error('Failed to seed reward config.');
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="saas-card animate-pulse flex flex-col justify-center p-5 space-y-4">
             <div className="flex justify-between w-full">
               <div className="h-3 bg-zinc-100 dark:bg-zinc-800 rounded w-1/3"></div>
               <div className="h-8 w-8 bg-zinc-100 dark:bg-zinc-800 rounded"></div>
             </div>
             <div className="h-6 bg-zinc-100 dark:bg-zinc-800 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  const needsConfigSeed = metrics.total_referrals > 0 && metrics.total_rewards_distributed === 0;

  return (
    <div className="space-y-6">
      {needsConfigSeed && (
        <div className="saas-card bg-amber-500/10 border-amber-500/20 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in slide-in-from-top-2">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-amber-500 tracking-tight">Missing Reward Configuration</h3>
              <p className="text-[13px] text-amber-500/80 mt-1">
                You have {metrics.total_referrals.toLocaleString()} valid referrals but ₹0.00 rewards distributed. 
                Seed the default configuration to backfill Missing payouts.
              </p>
            </div>
          </div>
          <button 
            onClick={handleSeedConfig}
            disabled={seeding}
            className="flex-shrink-0 bg-amber-500/20 hover:bg-amber-500/30 text-amber-500 border border-amber-500/20 px-4 py-2 rounded text-[13px] font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            {seeding && <Loader2 className="w-4 h-4 animate-spin" />}
            Seed Default Config
          </button>
        </div>
      )}
      <div className="grid grid-cols-1 justify-center sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-6">
        <MetricCard 
          title="Total Users" 
          value={metrics.total_users.toLocaleString()} 
          icon={Users} 
        />
        <MetricCard 
          title="Total Referrals" 
          value={metrics.total_referrals.toLocaleString()} 
          icon={TrendingUp} 
          accent={true}
        />
        <MetricCard 
          title="Rewards Distributed" 
          value={`₹${metrics.total_rewards_distributed.toLocaleString(undefined, { minimumFractionDigits: 2 })}`} 
          icon={DollarSign} 
          isCurrency={true}
        />
        <MetricCard 
          title="Accepted Claims" 
          value={metrics.accepted_claims.toLocaleString()} 
          icon={CheckCircle} 
        />
        <MetricCard 
          title="Rejected Claims" 
          value={metrics.rejected_claims.toLocaleString()} 
          icon={XCircle} 
        />
        <MetricCard 
          title="Fraud Alerts" 
          value={metrics.total_fraud_flags.toLocaleString()} 
          icon={AlertTriangle} 
        />
      </div>
    </div>
  );
};

export default MetricsPanel;
