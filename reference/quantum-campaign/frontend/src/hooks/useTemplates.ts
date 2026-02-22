import { useCallback, useEffect, useState } from 'react';
import type { TemplateListItem, ModuleInfo } from '../types';
import { fetchTemplates, fetchModules } from '../services/api';

export function useTemplates() {
  const [templates, setTemplates] = useState<TemplateListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTemplates();
      setTemplates(data.templates);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { templates, loading, reload: load };
}

export function useModules() {
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchModules()
      .then((d) => setModules(d.modules))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return { modules, loading };
}
