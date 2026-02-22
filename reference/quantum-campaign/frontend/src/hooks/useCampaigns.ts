import { useCallback, useEffect, useState } from 'react';
import type { CampaignListItem, CampaignListResponse } from '../types';
import { fetchCampaigns } from '../services/api';

interface Filters {
  account_id?: number;
  agency_name?: string;
  status?: string;
  page: number;
  limit: number;
}

export function useCampaigns(initialFilters?: Partial<Filters>) {
  const [filters, setFilters] = useState<Filters>({
    page: 1,
    limit: 50,
    ...initialFilters,
  });
  const [campaigns, setCampaigns] = useState<CampaignListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: CampaignListResponse = await fetchCampaigns(filters);
      setCampaigns(data.campaigns);
      setTotal(data.total);
      setPages(data.pages);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const updateFilters = useCallback(
    (patch: Partial<Filters>) =>
      setFilters((prev) => ({ ...prev, page: 1, ...patch })),
    [],
  );

  const setPage = useCallback(
    (page: number) => setFilters((prev) => ({ ...prev, page })),
    [],
  );

  return { campaigns, total, pages, page: filters.page, loading, updateFilters, setPage, reload: load };
}
