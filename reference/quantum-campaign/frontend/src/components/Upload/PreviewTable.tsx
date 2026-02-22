import { useState } from 'react';
import type { CampaignPreviewItem, CampaignConfirmItem } from '../../types';

interface PreviewTableProps {
  previews: CampaignPreviewItem[];
  onConfirm: (items: CampaignConfirmItem[]) => void;
  onCancel: () => void;
  confirming: boolean;
}

type ActionMap = Record<number, 'new' | 'extend'>;

export default function PreviewTable({
  previews,
  onConfirm,
  onCancel,
  confirming,
}: PreviewTableProps) {
  const [actions, setActions] = useState<ActionMap>(() => {
    const map: ActionMap = {};
    previews.forEach((p) => {
      map[p.row_number] = p.extension_eligible ? 'extend' : 'new';
    });
    return map;
  });

  const [checked, setChecked] = useState<Set<number>>(
    () => new Set(previews.filter((p) => p.is_valid).map((p) => p.row_number)),
  );

  const toggleCheck = (rowNum: number) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(rowNum)) next.delete(rowNum);
      else next.add(rowNum);
      return next;
    });
  };

  const toggleAll = () => {
    const validRows = previews.filter((p) => p.is_valid).map((p) => p.row_number);
    if (checked.size === validRows.length) {
      setChecked(new Set());
    } else {
      setChecked(new Set(validRows));
    }
  };

  const handleConfirm = () => {
    const items: CampaignConfirmItem[] = previews
      .filter((p) => checked.has(p.row_number) && p.is_valid)
      .map((p) => ({
        agency_name: p.agency_name,
        user_id: p.user_id,
        start_date: p.start_date,
        end_date: p.end_date,
        daily_limit: p.daily_limit,
        keywords: p.keywords,
        place_name: p.place_name,
        place_url: p.place_url,
        campaign_type: p.campaign_type,
        action: actions[p.row_number] || 'new',
        existing_campaign_id: actions[p.row_number] === 'extend' ? p.existing_campaign_id : null,
      }));
    onConfirm(items);
  };

  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b font-medium text-sm">
        미리보기 ({previews.length}건)
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={checked.size === previews.filter((p) => p.is_valid).length}
                  onChange={toggleAll}
                />
              </th>
              <th className="px-3 py-2 text-left font-medium">상호명</th>
              <th className="px-3 py-2 text-left font-medium">타입</th>
              <th className="px-3 py-2 text-left font-medium">기간</th>
              <th className="px-3 py-2 text-left font-medium">일일</th>
              <th className="px-3 py-2 text-left font-medium">연장가능</th>
              <th className="px-3 py-2 text-left font-medium">기존캠페인</th>
              <th className="px-3 py-2 text-left font-medium">선택</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {previews.map((p) => (
              <tr
                key={p.row_number}
                className={p.is_valid ? 'hover:bg-gray-50' : 'bg-red-50 opacity-60'}
              >
                <td className="px-3 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={checked.has(p.row_number)}
                    onChange={() => toggleCheck(p.row_number)}
                    disabled={!p.is_valid}
                  />
                </td>
                <td className="px-3 py-2 font-medium">
                  {p.place_name}
                  {p.errors.length > 0 && (
                    <div className="text-xs text-red-500 mt-0.5">{p.errors.join(', ')}</div>
                  )}
                </td>
                <td className="px-3 py-2">{p.campaign_type}</td>
                <td className="px-3 py-2 text-xs">
                  {p.start_date} ~ {p.end_date}
                </td>
                <td className="px-3 py-2">{p.daily_limit}</td>
                <td className="px-3 py-2">
                  {p.extension_eligible ? (
                    <span className="text-green-600 font-medium">가능</span>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
                <td className="px-3 py-2 text-xs font-mono">
                  {p.existing_campaign_code || '-'}
                </td>
                <td className="px-3 py-2">
                  {p.is_valid && p.extension_eligible ? (
                    <select
                      value={actions[p.row_number]}
                      onChange={(e) =>
                        setActions((prev) => ({
                          ...prev,
                          [p.row_number]: e.target.value as 'new' | 'extend',
                        }))
                      }
                      className="border rounded px-2 py-1 text-xs"
                    >
                      <option value="extend">연장</option>
                      <option value="new">신규</option>
                    </select>
                  ) : (
                    <span className="text-xs text-gray-500">신규</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end gap-2 px-4 py-3 border-t">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
        >
          취소
        </button>
        <button
          onClick={handleConfirm}
          disabled={confirming || checked.size === 0}
          className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
        >
          {confirming ? '등록 중...' : `최종 등록 (${checked.size}건)`}
        </button>
      </div>
    </div>
  );
}
