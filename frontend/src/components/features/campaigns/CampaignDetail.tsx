import type { Campaign, CampaignKeyword } from '@/types';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import {
  formatDate,
  formatDateTime,
  formatNumber,
  getCampaignStatusLabel,
  getCampaignTypeLabel,
} from '@/utils/format';

interface CampaignDetailProps {
  campaign: Campaign;
  keywords: CampaignKeyword[];
  onPause?: () => void;
  onResume?: () => void;
  onRotateKeywords?: () => void;
  actionLoading?: boolean;
}

function getStatusBadgeVariant(status: string) {
  const map: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'default',
    queued: 'info',
    registering: 'info',
    active: 'success',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
    expired: 'danger',
  };
  return map[status] || 'default';
}

export default function CampaignDetail({
  campaign,
  keywords,
  onPause,
  onResume,
  onRotateKeywords,
  actionLoading,
}: CampaignDetailProps) {
  const usedKeywords = keywords.filter((k) => k.is_used).length;
  const totalKeywords = keywords.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-surface rounded-xl border border-border p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-gray-100">
                {campaign.campaign_code || `캠페인 #${campaign.id}`}
              </h2>
              <Badge variant={getStatusBadgeVariant(campaign.status)}>
                {getCampaignStatusLabel(campaign.status)}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-gray-400">
              {campaign.place_name || '플레이스 정보 없음'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {campaign.status === 'active' && (
              <>
                <Button
                  variant="warning"
                  onClick={onPause}
                  loading={actionLoading}
                >
                  일시정지
                </Button>
                <Button
                  variant="secondary"
                  onClick={onRotateKeywords}
                  loading={actionLoading}
                >
                  키워드 교체
                </Button>
              </>
            )}
            {campaign.status === 'paused' && (
              <Button
                variant="success"
                onClick={onResume}
                loading={actionLoading}
              >
                재개
              </Button>
            )}
          </div>
        </div>

        {/* Info */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-gray-400 uppercase">기간</p>
            <p className="mt-1 text-sm font-medium text-gray-100">
              {campaign.start_date ? formatDate(campaign.start_date) : '-'} ~{' '}
              {campaign.end_date ? formatDate(campaign.end_date) : '-'}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase">일일 한도</p>
            <p className="mt-1 text-sm font-medium text-gray-100">
              {formatNumber(campaign.daily_limit)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase">캠페인 유형</p>
            <p className="mt-1 text-sm font-medium text-primary-600">
              {campaign.campaign_type ? getCampaignTypeLabel(campaign.campaign_type) : '-'}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase">전환수</p>
            <p className="mt-1 text-sm font-medium text-gray-100">
              {formatNumber(campaign.current_conversions)}
            </p>
          </div>
        </div>
      </div>

      {/* Keyword pool */}
      <div className="bg-surface rounded-xl border border-border">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-100">
            키워드 풀 ({totalKeywords}개)
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">
              사용: {usedKeywords} / {totalKeywords}
            </span>
            <div className="w-24 h-2 bg-surface-raised rounded-full overflow-hidden">
              <div
                className="h-full bg-primary-500 rounded-full transition-all"
                style={{
                  width: `${totalKeywords > 0 ? (usedKeywords / totalKeywords) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-surface-raised">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  키워드
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  라운드
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  사용 여부
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  사용일시
                </th>
              </tr>
            </thead>
            <tbody className="bg-surface divide-y divide-border">
              {keywords.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-6 py-8 text-center text-sm text-gray-400"
                  >
                    키워드가 없습니다.
                  </td>
                </tr>
              ) : (
                keywords.map((kw) => (
                  <tr key={kw.id}>
                    <td className="px-6 py-3 text-sm font-medium text-gray-100">
                      {kw.keyword}
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-400">
                      {kw.round_number}
                    </td>
                    <td className="px-6 py-3">
                      <Badge variant={kw.is_used ? 'default' : 'success'}>
                        {kw.is_used ? '사용됨' : '미사용'}
                      </Badge>
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-400">
                      {kw.used_at ? formatDateTime(kw.used_at) : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
