import { useState, useEffect } from 'react';
import Button from '@/components/common/Button';
import type { SystemSetting } from '@/types';
import { settingsApi } from '@/api/settings';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await settingsApi.list();
      setSettings(data);
      const values: Record<string, string> = {};
      data.forEach((s) => {
        values[s.key] = String(s.value ?? '');
      });
      setEditValues(values);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '설정을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async (key: string) => {
    setSavingKey(key);
    try {
      let value: any = editValues[key];
      // Try to parse as number or boolean
      if (value === 'true') value = true;
      else if (value === 'false') value = false;
      else if (!isNaN(Number(value)) && value.trim() !== '') value = Number(value);

      const updated = await settingsApi.update(key, { value });
      setSettings((prev) =>
        prev.map((s) => (s.key === key ? { ...s, value: updated.value, updated_at: updated.updated_at } : s)),
      );
    } catch (err: any) {
      alert(err?.response?.data?.detail || '설정 저장에 실패했습니다.');
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-white rounded-xl border border-gray-200 h-12" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 h-20" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">시스템 설정</h1>
        <p className="mt-1 text-sm text-gray-500">
          플랫폼 전역 설정을 관리합니다.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Settings list */}
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-200">
        {settings.map((setting) => {
          const currentValue = String(setting.value ?? '');
          return (
            <div
              key={setting.key}
              className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">
                  {setting.description || setting.key}
                </p>
                <p className="text-xs text-gray-500 font-mono mt-0.5">
                  {setting.key}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {currentValue === 'true' || currentValue === 'false' ? (
                  <select
                    value={editValues[setting.key]}
                    onChange={(e) =>
                      setEditValues({
                        ...editValues,
                        [setting.key]: e.target.value,
                      })
                    }
                    className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="true">활성화</option>
                    <option value="false">비활성화</option>
                  </select>
                ) : (
                  <input
                    type="text"
                    value={editValues[setting.key] || ''}
                    onChange={(e) =>
                      setEditValues({
                        ...editValues,
                        [setting.key]: e.target.value,
                      })
                    }
                    className="w-32 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  />
                )}
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleSave(setting.key)}
                  loading={savingKey === setting.key}
                  disabled={editValues[setting.key] === currentValue}
                >
                  저장
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
