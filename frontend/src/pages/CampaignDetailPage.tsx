import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import CampaignDetailComponent from '@/components/features/campaigns/CampaignDetail';
import Button from '@/components/common/Button';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import type { Campaign, CampaignKeyword } from '@/types';

// Mock data
const mockCampaign: Campaign = {
  id: 1,
  campaign_code: 'CMP-20260220-001',
  place: {
    id: 1,
    name: '맛있는 식당',
    category: '음식점',
    address: '서울 강남구 역삼동 123-45',
    url: 'https://map.naver.com/v5/entry/place/1234567890',
    created_at: '2026-02-20T00:00:00Z',
  },
  status: 'active',
  start_date: '2026-02-20',
  end_date: '2026-03-22',
  daily_limit: 100,
  total_budget: 300000,
  keywords_count: 8,
  current_keyword: '강남역 맛집',
  last_rotation_at: '2026-02-23T08:00:00Z',
  created_at: '2026-02-20T00:00:00Z',
};

const mockKeywords: CampaignKeyword[] = [
  { id: 1, campaign_id: 1, keyword: '강남역 맛집', is_used: true, used_at: '2026-02-23T08:00:00Z', rank: 3, last_rank_check: '2026-02-23T10:00:00Z' },
  { id: 2, campaign_id: 1, keyword: '역삼동 맛집', is_used: true, used_at: '2026-02-22T08:00:00Z', rank: 5, last_rank_check: '2026-02-23T10:00:00Z' },
  { id: 3, campaign_id: 1, keyword: '강남 점심 추천', is_used: true, used_at: '2026-02-21T08:00:00Z', rank: 8, last_rank_check: '2026-02-23T10:00:00Z' },
  { id: 4, campaign_id: 1, keyword: '강남역 근처 식당', is_used: false, rank: 12, last_rank_check: '2026-02-23T10:00:00Z' },
  { id: 5, campaign_id: 1, keyword: '역삼 점심', is_used: false, rank: 7, last_rank_check: '2026-02-23T10:00:00Z' },
  { id: 6, campaign_id: 1, keyword: '강남 맛있는 식당', is_used: false, rank: 15, last_rank_check: '2026-02-23T10:00:00Z' },
  { id: 7, campaign_id: 1, keyword: '강남역 회식', is_used: false, rank: 22, last_rank_check: '2026-02-23T10:00:00Z' },
  { id: 8, campaign_id: 1, keyword: '역삼 맛집 추천', is_used: false, rank: 4, last_rank_check: '2026-02-23T10:00:00Z' },
];

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [keywords, setKeywords] = useState<CampaignKeyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    // TODO: Replace with actual API call
    setTimeout(() => {
      setCampaign({ ...mockCampaign, id: Number(id) });
      setKeywords(mockKeywords);
      setLoading(false);
    }, 300);
  }, [id]);

  const handleAction = async (action: string) => {
    setActionLoading(true);
    console.log(`Action: ${action} on campaign ${id}`);
    // TODO: Call actual API
    setTimeout(() => {
      setActionLoading(false);
    }, 500);
  };

  if (loading || !campaign) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-white rounded-xl border border-gray-200 h-48" />
        <div className="bg-white rounded-xl border border-gray-200 h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/campaigns')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>
      </div>

      <CampaignDetailComponent
        campaign={campaign}
        keywords={keywords}
        onPause={() => handleAction('pause')}
        onResume={() => handleAction('resume')}
        onRotateKeywords={() => handleAction('rotate')}
        actionLoading={actionLoading}
      />
    </div>
  );
}
