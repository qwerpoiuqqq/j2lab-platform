import { useState, useEffect } from 'react';
import Button from '@/components/common/Button';
import type { SystemSetting } from '@/types';

// Mock data
const mockSettings: SystemSetting[] = [
  {
    key: 'max_concurrent_extractions',
    value: '5',
    description: '동시 추출 작업 최대 수',
    updated_at: '2026-02-20T10:00:00Z',
  },
  {
    key: 'max_keywords_per_extraction',
    value: '200',
    description: '추출당 최대 키워드 수',
    updated_at: '2026-02-20T10:00:00Z',
  },
  {
    key: 'keyword_rotation_interval',
    value: '10',
    description: '키워드 로테이션 체크 간격 (분)',
    updated_at: '2026-02-20T10:00:00Z',
  },
  {
    key: 'default_daily_limit',
    value: '100',
    description: '기본 일일 캠페인 한도',
    updated_at: '2026-02-20T10:00:00Z',
  },
  {
    key: 'auto_assign_enabled',
    value: 'true',
    description: '자동 배정 활성화',
    updated_at: '2026-02-20T10:00:00Z',
  },
  {
    key: 'proxy_rotation_enabled',
    value: 'true',
    description: '프록시 로테이션 활성화',
    updated_at: '2026-02-20T10:00:00Z',
  },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // TODO: Replace with actual API call
    setTimeout(() => {
      setSettings(mockSettings);
      const values: Record<string, string> = {};
      mockSettings.forEach((s) => {
        values[s.key] = s.value;
      });
      setEditValues(values);
      setLoading(false);
    }, 300);
  }, []);

  const handleSave = async (key: string) => {
    setSaving(true);
    console.log(`Save setting: ${key} = ${editValues[key]}`);
    // TODO: Call actual API
    setTimeout(() => {
      setSaving(false);
    }, 500);
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

      {/* Settings list */}
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-200">
        {settings.map((setting) => (
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
              {editValues[setting.key] === 'true' ||
              editValues[setting.key] === 'false' ? (
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
                loading={saving}
                disabled={editValues[setting.key] === setting.value}
              >
                저장
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
