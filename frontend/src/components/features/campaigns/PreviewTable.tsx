import { useState } from 'react';
import type { CampaignUploadPreviewItem } from '@/types';
import Button from '@/components/common/Button';
import { getCampaignTypeLabel } from '@/utils/format';

interface PreviewTableProps {
  previews: CampaignUploadPreviewItem[];
  onConfirm: (rowNumbers: number[]) => void;
  onCancel: () => void;
  confirming: boolean;
}

export default function PreviewTable({
  previews,
  onConfirm,
  onCancel,
  confirming,
}: PreviewTableProps) {
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

  const validRows = previews.filter((p) => p.is_valid);
  const toggleAll = () => {
    if (checked.size === validRows.length) {
      setChecked(new Set());
    } else {
      setChecked(new Set(validRows.map((p) => p.row_number)));
    }
  };

  const handleConfirm = () => {
    const selectedRows = previews
      .filter((p) => checked.has(p.row_number) && p.is_valid)
      .map((p) => p.row_number);
    onConfirm(selectedRows);
  };

  return (
    <div className="bg-surface rounded-xl border border-border overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex items-center justify-between">
        <span className="font-semibold text-sm text-gray-100">
          미리보기 ({previews.length}건)
        </span>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="text-green-600">{previews.filter((p) => p.is_valid).length}건 정상</span>
          {previews.filter((p) => !p.is_valid).length > 0 && (
            <span className="text-red-600">{previews.filter((p) => !p.is_valid).length}건 오류</span>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-raised">
            <tr>
              <th className="px-3 py-2.5 text-center w-8">
                <input
                  type="checkbox"
                  checked={checked.size > 0 && checked.size === validRows.length}
                  onChange={toggleAll}
                  className="rounded border-border-strong"
                />
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-400 uppercase">상호명</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-400 uppercase">타입</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-400 uppercase">기간</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-400 uppercase">일일</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-400 uppercase">키워드</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-400 uppercase">연장</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-400 uppercase">기존캠페인</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {previews.map((p) => (
              <tr
                key={p.row_number}
                className={p.is_valid ? 'hover:bg-surface-raised' : 'bg-red-900/20 opacity-60'}
              >
                <td className="px-3 py-2.5 text-center">
                  <input
                    type="checkbox"
                    checked={checked.has(p.row_number)}
                    onChange={() => toggleCheck(p.row_number)}
                    disabled={!p.is_valid}
                    className="rounded border-border-strong"
                  />
                </td>
                <td className="px-3 py-2.5 font-medium text-gray-100">
                  {p.place_name || '-'}
                  {p.errors.length > 0 && (
                    <div className="text-xs text-red-500 mt-0.5">{p.errors.join(', ')}</div>
                  )}
                </td>
                <td className="px-3 py-2.5 text-gray-400">{getCampaignTypeLabel(p.campaign_type)}</td>
                <td className="px-3 py-2.5 text-gray-400 text-xs">
                  {p.start_date} ~ {p.end_date}
                </td>
                <td className="px-3 py-2.5 text-gray-400">{p.daily_limit}</td>
                <td className="px-3 py-2.5 text-gray-400 text-xs">{p.keyword_count}개</td>
                <td className="px-3 py-2.5">
                  {p.extension_eligible ? (
                    <span className="text-green-600 font-medium text-xs">가능</span>
                  ) : (
                    <span className="text-gray-400 text-xs">-</span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-xs font-mono text-gray-400">
                  {p.existing_campaign_code || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end gap-3 px-5 py-3 border-t border-border">
        <Button variant="secondary" onClick={onCancel}>
          취소
        </Button>
        <Button
          variant="primary"
          onClick={handleConfirm}
          loading={confirming}
          disabled={checked.size === 0}
        >
          {confirming ? '등록 중...' : `최종 등록 (${checked.size}건)`}
        </Button>
      </div>
    </div>
  );
}
