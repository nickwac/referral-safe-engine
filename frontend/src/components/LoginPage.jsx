import React, { useState } from 'react';
import { LockKeyhole, Mail, Shield } from 'lucide-react';
import toast from 'react-hot-toast';
import { loginAdmin } from '../api';

const LoginPage = ({ onAuthenticated }) => {
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    try {
      const data = await loginAdmin({ email, password });
      onAuthenticated?.({
        admin_id: data.admin_id,
        email: data.email,
        role: data.role,
        org_id: data.org_id,
        org_name: data.org_name,
      });
      toast.success('Signed in');
    } catch (error) {
      const message = error.response?.data?.detail?.message || 'Login failed';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md saas-card p-8 space-y-6">
        <div className="space-y-3 text-center">
          <div className="mx-auto w-14 h-14 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 flex items-center justify-center shadow-[0_0_40px_rgba(34,211,238,0.12)]">
            <Shield className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Admin Sign In</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-2">Authenticate before accessing organisation-scoped metrics, fraud alerts, and DAG operations.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold">Email</span>
            <div className="mt-2 flex items-center gap-3 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/80 px-4 py-3">
              <Mail className="w-4 h-4 text-zinc-500" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-transparent outline-none text-sm text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-600"
                placeholder="admin@example.com"
                autoComplete="username"
              />
            </div>
          </label>

          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold">Password</span>
            <div className="mt-2 flex items-center gap-3 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/80 px-4 py-3">
              <LockKeyhole className="w-4 h-4 text-zinc-500" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-transparent outline-none text-sm text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-600"
                placeholder="Enter your password"
                autoComplete="current-password"
              />
            </div>
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-cyan-500 text-zinc-950 font-semibold py-3 transition hover:bg-cyan-400 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/70 p-4 text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
          <p><span className="text-zinc-800 dark:text-zinc-200 font-medium">Org Admin:</span> `admin@example.com` / `admin123`</p>
          <p><span className="text-zinc-800 dark:text-zinc-200 font-medium">Super Admin:</span> `owner@example.com` / `Owner123!`</p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
