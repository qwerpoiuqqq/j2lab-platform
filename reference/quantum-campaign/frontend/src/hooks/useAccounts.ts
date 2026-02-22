import { useCallback, useEffect, useState } from 'react';
import type { Account, Agency, DashboardStats } from '../types';
import { fetchAccounts, fetchAgencies, fetchDashboardStats } from '../services/api';

export function useAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAccounts();
      setAccounts(data.accounts);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { accounts, loading, reload: load };
}

export function useAgencies() {
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgencies()
      .then((d) => setAgencies(d.agencies))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return { agencies, loading };
}

export function useDashboardStats(accountId?: number) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchDashboardStats(accountId);
      setStats(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => { load(); }, [load]);

  return { stats, loading, reload: load };
}
