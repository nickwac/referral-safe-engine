import React, { useEffect, useState, useRef } from 'react';
import { getRecentActivity, getWebsocketUrl } from '../api';
import { Activity, UserPlus, Zap, AlertTriangle, MessageSquare, Copy, ExternalLink } from 'lucide-react';
import { format } from 'date-fns';
import toast from 'react-hot-toast';

const EventIcon = ({ type }) => {
  switch (type) {
    case 'referral_claimed':
    case 'referral_accepted':
      return <UserPlus className="w-4 h-4 text-emerald-500" />;
    case 'reward_paid':
      return <Zap className="w-4 h-4 text-indigo-400" />;
    case 'fraud_flag':
    case 'fraud_prevented':
    case 'cycle_prevented':
    case 'velocity_detected':
      return <AlertTriangle className="w-4 h-4 text-red-400" />;
    default:
      return <MessageSquare className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />;
  }
};

const pickUserId = (event) => event?.payload?.user_id || event?.payload?.child_id || event?.payload?.beneficiary_id || null;

const formatEventTitle = (type) => {
  const titles = {
    referral_claimed: 'Referral Claimed',
    referral_accepted: 'Referral Accepted',
    reward_paid: 'Reward Distributed',
    fraud_flag: 'Fraud Flag Raised',
    cycle_prevented: 'Cycle Prevented',
    velocity_detected: 'Velocity Violation Detected',
    seed_completed: 'Seed Completed',
  };
  return titles[type] || type.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
};

const formatEventDescription = (event) => {
  const payload = event.payload || {};
  switch (event.event_type) {
    case 'referral_claimed':
    case 'referral_accepted':
      return `Referral created from ${String(payload.parent_id || '').slice(0, 8)} to ${String(payload.child_id || '').slice(0, 8)}.`;
    case 'reward_paid':
      return `Paid ${payload.amount ?? 0} at level ${payload.level ?? '-'} to ${String(payload.beneficiary_id || '').slice(0, 8)}.`;
    case 'fraud_flag':
      return `${String(payload.reason || 'fraud').replaceAll('_', ' ')} blocked for ${String(payload.user_id || '').slice(0, 8)}.`;
    case 'cycle_prevented':
      return `${payload.attempts ?? 0} cycle attempts were blocked during seed setup.`;
    case 'velocity_detected':
      return `${payload.attempts ?? 0} velocity violations were logged during seed setup.`;
    case 'seed_completed':
      return `Loaded ${payload.users ?? 0} users and ${payload.valid_referrals ?? 0} referrals.`;
    default:
      return Object.entries(payload).map(([key, value]) => `${key}: ${value}`).join(' | ');
  }
};

const ActivityFeed = ({ onSelectUser }) => {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('connecting');
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const fetchInitialActivity = async () => {
    try {
      const data = await getRecentActivity();
      setEvents(data || []);
    } catch (e) {
      console.error('Failed to load initial activity:', e);
    }
  };

  const connectWebSocket = () => {
    if (wsRef.current) return;

    const wsUrl = getWebsocketUrl();
    if (!wsUrl) {
      setStatus('disconnected');
      return;
    }

    setStatus('connecting');
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setStatus('connected');
    };

    ws.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data);
        setEvents((prev) => [event, ...prev].slice(0, 50));
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (e) => {
      console.error('Activity WS error:', e);
      ws.close();
    };

    wsRef.current = ws;
  };

  useEffect(() => {
    fetchInitialActivity();
    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, []);

  const handleCopy = async (userId) => {
    if (!userId) return;
    await navigator.clipboard.writeText(userId);
    toast.success('User UUID copied');
  };

  const handleOpen = (userId) => {
    if (!userId) return;
    onSelectUser?.(userId, 'Activity Feed');
    toast.success('Loaded in DAG Explorer');
  };

  return (
    <div className="saas-card flex flex-col h-[400px] overflow-hidden">
      <div className="p-6 border-b border-zinc-200 dark:border-zinc-800/60 bg-zinc-50 dark:bg-zinc-950/50 flex flex-row items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-center">
            <Activity className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">Activity Feed</h2>
            <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-widest mt-0.5">Live Websocket</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {status === 'connected' ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-40"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          ) : (
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500/80"></span>
          )}
          <span className="text-[10px] text-zinc-500 dark:text-zinc-400 font-semibold uppercase tracking-wider">{status}</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-zinc-50 dark:bg-zinc-950/20">
        {events.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-zinc-600">
            <Activity className="w-8 h-8 mb-3 opacity-20" />
            <p className="text-sm">Awaiting payload...</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/40">
            {events.map((evt, idx) => {
              const userId = pickUserId(evt);
              return (
                <div key={evt.id || idx} className="p-4 flex gap-4 hover:bg-white dark:bg-zinc-900/40 transition-colors animate-in fade-in slide-in-from-top-2 duration-300">
                  <div className="mt-1 flex-shrink-0 w-8 h-8 rounded-full border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-center">
                    <EventIcon type={evt.event_type} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium text-zinc-800 dark:text-zinc-200 tracking-tight">{formatEventTitle(evt.event_type)}</p>
                    <p className="text-[12px] text-zinc-500 tracking-tight mt-0.5 break-words">{formatEventDescription(evt)}</p>
                    {userId && (
                      <div className="mt-2 flex items-center gap-2 text-zinc-500">
                        <button type="button" onClick={() => handleCopy(userId)} title="Copy full UUID" className="hover:text-zinc-800 dark:text-zinc-200 transition-colors">
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        <button type="button" onClick={() => handleOpen(userId)} title="Open in DAG explorer" className="hover:text-zinc-800 dark:text-zinc-200 transition-colors">
                          <ExternalLink className="w-3.5 h-3.5" />
                        </button>
                        <span className="text-[11px] font-mono">{userId.slice(0, 8)}...</span>
                      </div>
                    )}
                  </div>
                  <div className="text-[11px] font-mono text-zinc-600 whitespace-nowrap self-start mt-1">
                    {evt.created_at ? format(new Date(evt.created_at), 'HH:mm:ss') : 'Now'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityFeed;
