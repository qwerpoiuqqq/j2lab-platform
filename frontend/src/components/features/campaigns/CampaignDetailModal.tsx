import { useEffect, useState } from 'react';
import Modal from '@/components/common/Modal';
import Button from '@/components/common/Button';
import { campaignsApi } from '@/api/campaigns';
import type { Campaign, CampaignKeyword } from '@/types';
import { getCampaignExtendedStatusLabel, getCampaignExtendedStatusColor, getCampaignTypeLabel } from '@/utils/format';

interface CampaignDetailModalProps {
  campaignId: number;
  onClose: () => void;
}

function fmtDate(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  return dateStr.slice(0, 10);
}

function fmtDateTime(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  return dateStr.slice(0, 16).replace('T', ' ');
}

export default function CampaignDetailModal({ campaignId, onClose }: CampaignDetailModalProps) {
  const [detail, setDetail] = useState<Campaign | null>(null);
  const [keywords, setKeywords] = useState<CampaignKeyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([campaignsApi.get(campaignId), campaignsApi.getKeywords(campaignId)])
      .then(([camp, kws]) => {
        if (!cancelled) {
          setDetail(camp);
          setKeywords(kws.items);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e?.response?.data?.detail || '불러오기 실패');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [campaignId]);

  const usedCount = keywords.filter((k) => k.is_used).length;
  const remainingCount = keywords.length - usedCount;
  const remainingDays = detail
    ? Math.max(0, Math.ceil((new Date(detail.end_date).getTime() - Date.now()) / 86400000) + 1)
    : 0;
  const ratio = remainingDays > 0 ? (remainingCount / remainingDays).toFixed(1) : null;

  return (
    <Modal isOpen onClose={onClose} title="캠페인 상세" size="xl">
      {loading ? (
        <div className="py-12 text-center text-gray-500">로딩 중...</div>
      ) : error ? (
        <div className="py-12 text-center text-red-500">{error}</div>
      ) : detail ? (
        <div className="space-y-5">
          {/* Basic info */}
          <Section title="기본 정보">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2">
              <InfoItem label="상호명" value={detail.place_name} />
              <InfoItem label="캠페인코드" value={detail.campaign_code || '-'} mono />
              <InfoItem label="캠페인 타입" value={detail.campaign_type ? getCampaignTypeLabel(detail.campaign_type) : '-'} />
              <div className="text-sm">
                <span className="text-gray-500">상태: </span>
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${getCampaignExtendedStatusColor(detail.status)}`}>
                  {getCampaignExtendedStatusLabel(detail.status)}
                </span>
              </div>
              <InfoItem label="일일한도" value={`${detail.daily_limit}건`} />
              <InfoItem
                label="전환수"
                value={`${detail.current_conversions}${detail.total_limit ? `/${detail.total_limit}` : ''}`}
              />
            </div>
          </Section>

          {/* Dates */}
          <Section title="날짜">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2">
              <InfoItem label="시작일" value={fmtDate(detail.start_date)} />
              <InfoItem label="마감일" value={fmtDate(detail.end_date)} />
              <InfoItem label="등록일" value={fmtDateTime(detail.registered_at)} />
            </div>
          </Section>

          {/* Keyword status */}
          <Section title="키워드 현황">
            <div className="flex gap-3 mb-4">
              <StatCard label="전체" value={keywords.length} color="blue" />
              <StatCard label="사용됨" value={usedCount} color="gray" />
              <StatCard label="남은 수" value={remainingCount} color="green" />
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-600 mb-4">
              <span>남은 일수: <strong>{remainingDays}일</strong></span>
              {ratio && (
                <span>
                  일 평균 여유: <strong>{ratio}개/일</strong>
                  {parseFloat(ratio) < 1 && (
                    <span className="text-red-500 ml-1">(부족)</span>
                  )}
                </span>
              )}
            </div>

            {keywords.length > 0 ? (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">
                  키워드 목록 ({keywords.length}개)
                </div>
                <div className="max-h-60 overflow-auto border rounded-lg">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-600 w-12">#</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">키워드</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600 w-20">상태</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600 w-28">사용일</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {keywords.map((kw, idx) => (
                        <tr key={kw.id} className={kw.is_used ? 'bg-gray-50/50 text-gray-400' : ''}>
                          <td className="px-3 py-1.5 text-gray-400">{idx + 1}</td>
                          <td className="px-3 py-1.5 font-mono">{kw.keyword}</td>
                          <td className="px-3 py-1.5">
                            {kw.is_used ? (
                              <span className="text-gray-400">사용됨</span>
                            ) : (
                              <span className="text-green-600 font-medium">미사용</span>
                            )}
                          </td>
                          <td className="px-3 py-1.5 text-gray-400">
                            {kw.used_at ? fmtDate(kw.used_at) : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400 italic">
                등록된 키워드가 없습니다.
              </div>
            )}
          </Section>

          <div className="flex justify-end pt-2">
            <Button variant="secondary" onClick={onClose}>
              닫기
            </Button>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-800 mb-2 pb-1 border-b">{title}</h3>
      {children}
    </div>
  );
}

function InfoItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="text-sm">
      <span className="text-gray-500">{label}: </span>
      <span className={`font-medium ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: 'blue' | 'gray' | 'green' }) {
  const colorMap = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
    green: 'bg-green-50 text-green-700 border-green-200',
  };
  return (
    <div className={`flex-1 text-center px-4 py-3 rounded-lg border ${colorMap[color]}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs mt-0.5">{label}</div>
    </div>
  );
}
