import React, { useCallback, useEffect, useRef, useState } from 'react';
import { searchUsers } from '../api';
import { Loader2, Search, User, CheckCircle } from 'lucide-react';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const StatusPip = ({ status }) => {
  const colors = {
    active: 'bg-emerald-500',
    flagged: 'bg-red-500',
    root: 'bg-indigo-500',
    inactive: 'bg-zinc-500',
    suspended: 'bg-amber-500',
    banned: 'bg-red-700',
  };
  return (
    <span
      title={status}
      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${colors[status] ?? 'bg-zinc-500'}`}
    />
  );
};

/**
 * UserSearchCombobox — replaces the raw UUID input in the DAG Explorer.
 *
 * Props:
 *   value        string          — current selected user ID (controlled)
 *   onChange     (id) => void    — called with user ID when a user is selected
 *   placeholder  string          — input placeholder text
 *   className    string          — extra classes on the wrapper
 */
const UserSearchCombobox = ({ value, onChange, placeholder = 'Search by name, email, or UUID…', className = '' }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const [error, setError] = useState('');

  const inputRef = useRef(null);
  const listRef = useRef(null);
  const debounceRef = useRef(null);

  // When external value changes (e.g. click from FraudMonitor), update display
  useEffect(() => {
    if (!value) {
      setQuery('');
      setSelectedLabel('');
    }
  }, [value]);

  const runSearch = useCallback(async (q) => {
    if (!q || q.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await searchUsers(q, 10);
      setResults(data);
      setOpen(true);
      setHighlightIdx(-1);
    } catch (err) {
      console.error('Search failed:', err);
      setError('Search failed — is the backend running?');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInputChange = (e) => {
    const q = e.target.value;
    setQuery(q);
    setSelectedLabel('');

    // If user pastes a full UUID, select it immediately without searching
    if (UUID_REGEX.test(q.trim())) {
      onChange(q.trim());
      setOpen(false);
      return;
    }

    clearTimeout(debounceRef.current);
    if (q.length >= 1) {
      debounceRef.current = setTimeout(() => runSearch(q), 300);
    } else {
      setResults([]);
      setOpen(false);
    }
  };

  const handleSelect = (user) => {
    setQuery(`${user.username}`);
    setSelectedLabel(`${user.username} · ${user.email}`);
    setOpen(false);
    setResults([]);
    onChange(user.id);
  };

  const handleKeyDown = (e) => {
    if (!open || results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && highlightIdx >= 0) {
      e.preventDefault();
      handleSelect(results[highlightIdx]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const handleBlur = (e) => {
    // Close only if focus leaves the entire combobox container
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setOpen(false);
    }
  };

  return (
    <div
      className={`relative ${className}`}
      onBlur={handleBlur}
    >
      <div className="relative flex items-center">
        {loading ? (
          <Loader2 className="absolute left-3 w-4 h-4 text-zinc-500 animate-spin pointer-events-none" />
        ) : (
          <Search className="absolute left-3 w-4 h-4 text-zinc-600 pointer-events-none" />
        )}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length >= 1 && results.length > 0 && setOpen(true)}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className="w-full pl-9 pr-4 py-1.5 bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-800 dark:text-zinc-200 text-sm rounded 
            focus:outline-none focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600 
            placeholder-zinc-600 font-mono transition-colors"
        />
        {value && !open && (
          <CheckCircle className="absolute right-3 w-3.5 h-3.5 text-emerald-500 pointer-events-none" />
        )}
      </div>

      {/* Dropdown */}
      {open && (
        <div
          ref={listRef}
          className="absolute z-50 top-full mt-1.5 left-0 right-0 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded shadow-xl shadow-black/50 overflow-hidden"
        >
          {error ? (
            <div className="px-4 py-3 text-sm text-red-400">{error}</div>
          ) : results.length === 0 && !loading ? (
            <div className="px-4 py-3 text-sm text-zinc-500 flex items-center gap-2">
              <User className="w-4 h-4" />
              No users found for "{query}"
            </div>
          ) : (
            <ul>
              {results.map((user, idx) => (
                <li key={user.id}>
                  <button
                    type="button"
                    tabIndex={0}
                    onClick={() => handleSelect(user)}
                    className={`w-full text-left px-4 py-2.5 flex items-center gap-3 transition-colors text-sm
                      ${idx === highlightIdx ? 'bg-zinc-100 dark:bg-zinc-800' : 'hover:bg-zinc-100 dark:bg-zinc-800/70'}`}
                  >
                    <StatusPip status={user.status} />
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-zinc-800 dark:text-zinc-200 block truncate">{user.username}</span>
                      <span className="text-zinc-500 text-[11px] font-mono truncate block">{user.email}</span>
                    </div>
                    <span className="text-zinc-600 text-[10px] font-mono flex-shrink-0 hidden sm:block">
                      {user.id.substring(0, 8)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default UserSearchCombobox;
