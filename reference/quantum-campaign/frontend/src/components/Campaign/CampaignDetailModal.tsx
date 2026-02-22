import { useEffect, useState } from 'react';
import Modal from '../common/Modal';
import { fetchCampaignDetail, getErrorMessage } from '../../services/api';
import type { CampaignDetail } from '../../types';

interface CampaignDetailModalProps {
  campaignId: number;
  onClose: () => void;
}

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  return dateStr.slice(0, 10);
}

function formatDateTime(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  return dateStr.slice(0, 16).replace('T', ' ');
}

export default function CampaignDetailModal({ campaignId, onClose }: CampaignDetailModalProps) {
  const [detail, setDetail] = useState<CampaignDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCampaignDetail(campaignId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled) setError(getErrorMessage(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [campaignId]);

  const remainingDays = detail
    ? Math.max(0, Math.ceil((new Date(detail.end_date).getTime() - Date.now()) / 86400000) + 1)
    : 0;

  const ratio = detail && remainingDays > 0
    ? (detail.keyword_remaining / remainingDays).toFixed(1)
    : null;

  return (
    <Modal open={true} onClose={onClose} title="캠페인 상세" wide>
      {loading ? (
        <div className="py-12 text-center text-gray-500">로딩 중...</div>
      ) : error ? (
        <div className="py-12 text-center text-red-500">{error}</div>
      ) : detail ? (
        <div className="space-y-5">
          {/* 기본 정보 */}
          <Section title="기본 정보">
            <InfoGrid>
              <InfoItem label="상호명" value={detail.place_name} />
              <InfoItem label="캠페인코드" value={detail.campaign_code || '-'} mono />
              <InfoItem label="캠페인 타입" value={detail.campaign_type} />
              <InfoItem label="상태" value={detail.status} badge />
              <InfoItem label="일일한도" value={`${detail.daily_limit}건`} />
              <InfoItem
                label="전환수"
                value={`${detail.current_conversions}${detail.total_limit ? `/${detail.total_limit}` : ''}`}
              />
            </InfoGrid>
          </Section>

          {/* 날짜 */}
          <Section title="날짜">
            <InfoGrid>
              <InfoItem label="시작일" value={formatDate(detail.start_date)} />
              <InfoItem label="마감일" value={formatDate(detail.end_date)} />
              <InfoItem label="등록일" value={formatDateTime(detail.registered_at)} />
              <InfoItem label="진행일수" value={detail.days_running > 0 ? `D+${detail.days_running}` : '-'} />
            </InfoGrid>
            {detail.extension_history && detail.extension_history.length > 0 && (
              <div className="mt-3 p-3 bg-purple-50 rounded-md">
                <div className="text-sm font-medium text-purple-700 mb-2">
                  연장 이력 ({detail.extension_history.length}회)
                </div>
                <div className="space-y-1">
                  {detail.extension_history.map((ext) => (
                    <div key={ext.round} className="text-xs text-purple-600 flex items-center gap-2">
                      <span className="font-medium">연장 {ext.round}회</span>
                      <span>{ext.start_date} ~ {ext.end_date}</span>
                      <span className="text-purple-500">일 {ext.daily_limit}타</span>
                      {ext.keywords_added > 0 && (
                        <span className="text-purple-400">+키워드 {ext.keywords_added}개</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Section>

          {/* 키워드 현황 */}
          <Section title="키워드 현황">
            <div className="flex gap-3 mb-4">
              <StatCard label="전체" value={detail.keyword_total} color="blue" />
              <StatCard label="사용됨" value={detail.keyword_used} color="gray" />
              <StatCard label="남은 수" value={detail.keyword_remaining} color="green" />
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
              <KeywordStatusBadge status={detail.keyword_status} />
            </div>

            {/* 키워드 목록 */}
            {detail.keywords.length > 0 ? (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">
                  키워드 목록 ({detail.keywords.length}개)
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
                      {detail.keywords.map((kw, idx) => (
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
                            {kw.used_at ? formatDate(kw.used_at) : '-'}
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
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
            >
              닫기
            </button>
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

function InfoGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2">{children}</div>;
}

function InfoItem({ label, value, mono, badge }: { label: string; value: string; mono?: boolean; badge?: boolean }) {
  return (
    <div className="text-sm">
      <span className="text-gray-500">{label}: </span>
      {badge ? (
        <StatusBadge status={value} />
      ) : (
        <span className={`font-medium ${mono ? 'font-mono' : ''}`}>{value}</span>
      )}
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

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: 'bg-green-100 text-green-800',
    pending: 'bg-gray-100 text-gray-600',
    pending_extend: 'bg-purple-100 text-purple-800',
  };
  const cls = map[status] || 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

function KeywordStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    normal: { label: '충분', cls: 'bg-green-100 text-green-800' },
    warning: { label: '주의', cls: 'bg-yellow-100 text-yellow-800' },
    critical: { label: '부족', cls: 'bg-red-100 text-red-800' },
  };
  const cfg = map[status] || map.normal;
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}
