import React, { useEffect, useState } from 'react';
import { BadgeIndianRupee, Ban, Clock3, ShieldAlert, UserRoundSearch } from 'lucide-react';
import { format } from 'date-fns';
import toast from 'react-hot-toast';
import { getUserProfile, updateUserStatus } from '../api';
import UserSearchCombobox from './UserSearchCombobox';

const statusOptions = [
  { value: 'active', label: 'Set Active' },
  { value: 'suspended', label: 'Suspend' },
  { value: 'banned', label: 'Ban' },
  { value: 'flagged', label: 'Flag' },
];

const UserProfilePanel = ({ selectedUserId, onSelectUser }) => {
  const [userId, setUserId] = useState(selectedUserId || '');
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reason, setReason] = useState('');
  const [updating, setUpdating] = useState('');

  const loadProfile = async (targetUserId) => {
    if (!targetUserId) return;
    setLoading(true);
    try {
      const data = await getUserProfile(targetUserId);
      setProfile(data);
      setUserId(targetUserId);
    } catch (error) {
      console.error(error);
      setProfile(null);
      toast.error('Failed to load user profile');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedUserId && selectedUserId !== userId) {
      loadProfile(selectedUserId);
    }
  }, [selectedUserId]);

  const handleStatusChange = async (nextStatus) => {
    if (!profile?.user?.id) return;
    if (reason.trim().length < 5) {
      toast.error('Add a reason before changing status');
      return;
    }
    setUpdating(nextStatus);
    try {
      const updated = await updateUserStatus(profile.user.id, { status: nextStatus, reason });
      setProfile((prev) => ({ ...prev, user: updated }));
      setReason('');
      toast.success(`User marked ${nextStatus}`);
    } catch (error) {
      console.error(error);
      toast.error('Status update failed');
    } finally {
      setUpdating('');
    }
  };

  return (
    <section className="saas-card p-6 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">User Profile</h2>
          <p className="text-sm text-zinc-500 mt-1">Search any user, inspect their claim history, fraud trail, and take status actions.</p>
        </div>
        <div className="w-full max-w-sm">
          <UserSearchCombobox
            value={userId}
            onChange={(id) => {
              setUserId(id);
              onSelectUser?.(id, 'User Profile');
              loadProfile(id);
            }}
            placeholder="Search a user for profile lookup..."
          />
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="h-44 rounded-xl bg-white dark:bg-zinc-900/60 animate-pulse" />
          <div className="h-44 rounded-xl bg-white dark:bg-zinc-900/60 animate-pulse" />
        </div>
      ) : !profile ? (
        <div className="rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/40 p-10 text-center text-zinc-500">
          <UserRoundSearch className="w-8 h-8 mx-auto mb-3 text-zinc-700" />
          Choose a user from the DAG explorer flow or search directly here.
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">{profile.user.username}</h3>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">{profile.user.email}</p>
                  <p className="text-xs font-mono text-zinc-600 mt-2 break-all">{profile.user.id}</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs uppercase tracking-[0.18em] bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300">{profile.user.status}</span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
                <div className="rounded-lg bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-zinc-800 p-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Balance</p>
                  <p className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-1">?{profile.user.reward_balance.toFixed(2)}</p>
                </div>
                <div className="rounded-lg bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-zinc-800 p-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Claims</p>
                  <p className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-1">{profile.recent_claims.length}</p>
                </div>
                <div className="rounded-lg bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-zinc-800 p-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Fraud Flags</p>
                  <p className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-1">{profile.fraud_flags.length}</p>
                </div>
                <div className="rounded-lg bg-white dark:bg-zinc-900/80 border border-zinc-200 dark:border-zinc-800 p-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Joined</p>
                  <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-1">{format(new Date(profile.user.created_at), 'MMM dd, yyyy')}</p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-5 space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">Status Actions</h3>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={4}
                placeholder="Reason for status change..."
                className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200 outline-none focus:border-zinc-600"
              />
              <div className="grid grid-cols-2 gap-2">
                {statusOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => handleStatusChange(option.value)}
                    disabled={updating === option.value}
                    className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200 hover:border-zinc-600 transition-colors disabled:opacity-60"
                  >
                    {updating === option.value ? 'Updating...' : option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-5">
              <div className="flex items-center gap-2 mb-4 text-zinc-800 dark:text-zinc-200"><BadgeIndianRupee className="w-4 h-4" /> Recent Rewards</div>
              <div className="space-y-3 max-h-72 overflow-auto">
                {profile.recent_transactions.length === 0 ? <p className="text-sm text-zinc-500">No transactions yet.</p> : profile.recent_transactions.map((txn) => (
                  <div key={txn.id} className="rounded-lg bg-white dark:bg-zinc-900/70 border border-zinc-200 dark:border-zinc-800 p-3 text-sm">
                    <div className="flex justify-between gap-3"><span className="text-zinc-800 dark:text-zinc-200">?{txn.amount.toFixed(2)}</span><span className="text-zinc-500">L{txn.level}</span></div>
                    <p className="text-zinc-500 mt-1">{format(new Date(txn.created_at), 'MMM dd, HH:mm')}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-5">
              <div className="flex items-center gap-2 mb-4 text-zinc-800 dark:text-zinc-200"><Clock3 className="w-4 h-4" /> Recent Claims</div>
              <div className="space-y-3 max-h-72 overflow-auto">
                {profile.recent_claims.length === 0 ? <p className="text-sm text-zinc-500">No referral claims found.</p> : profile.recent_claims.map((claim) => (
                  <div key={claim.id} className="rounded-lg bg-white dark:bg-zinc-900/70 border border-zinc-200 dark:border-zinc-800 p-3 text-sm">
                    <div className="flex justify-between gap-3 text-zinc-800 dark:text-zinc-200"><span>{claim.status}</span><span>{format(new Date(claim.created_at), 'MMM dd, HH:mm')}</span></div>
                    <p className="text-zinc-500 mt-1 font-mono break-all">{claim.parent_id} ? {claim.child_id}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/70 p-5">
              <div className="flex items-center gap-2 mb-4 text-zinc-800 dark:text-zinc-200"><ShieldAlert className="w-4 h-4" /> Fraud & Audit</div>
              <div className="space-y-3 max-h-72 overflow-auto">
                {profile.fraud_flags.map((flag) => (
                  <div key={flag.id} className="rounded-lg bg-red-950/10 border border-red-900/30 p-3 text-sm">
                    <div className="flex justify-between gap-3"><span className="text-red-300 uppercase tracking-wide">{flag.reason}</span><span className="text-zinc-500">{format(new Date(flag.timestamp), 'MMM dd')}</span></div>
                    <p className="text-zinc-500 dark:text-zinc-400 mt-1">{flag.detail || 'No detail provided'}</p>
                  </div>
                ))}
                {profile.audit_entries.map((entry) => (
                  <div key={entry.id} className="rounded-lg bg-white dark:bg-zinc-900/70 border border-zinc-200 dark:border-zinc-800 p-3 text-sm">
                    <p className="text-zinc-800 dark:text-zinc-200">{entry.action}</p>
                    <p className="text-zinc-500 mt-1">{format(new Date(entry.timestamp), 'MMM dd, HH:mm')}</p>
                  </div>
                ))}
                {profile.fraud_flags.length === 0 && profile.audit_entries.length === 0 && <p className="text-sm text-zinc-500">No fraud or audit events linked to this user.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default UserProfilePanel;
