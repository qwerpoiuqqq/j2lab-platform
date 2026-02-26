import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import CampaignDetailComponent from '@/components/features/campaigns/CampaignDetail';
import Button from '@/components/common/Button';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import type { Campaign, CampaignKeyword } from '@/types';
import { campaignsApi } from '@/api/campaigns';

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [keywords, setKeywords] = useState<CampaignKeyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadCampaign = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [campaignData, keywordsData] = await Promise.all([
        campaignsApi.get(Number(id)),
        campaignsApi.getKeywords(Number(id)),
      ]);
      setCampaign(campaignData);
      setKeywords(keywordsData.items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '캠페인을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCampaign();
  }, [id]);

  const handleAction = async (action: string) => {
    if (!id) return;
    setActionLoading(true);
    try {
      let updated: Campaign;
      switch (action) {
        case 'pause':
          updated = await campaignsApi.pause(Number(id));
          break;
        case 'resume':
          updated = await campaignsApi.resume(Number(id));
          break;
        case 'rotate':
          updated = await campaignsApi.rotateKeywords(Number(id));
          break;
        default:
          setActionLoading(false);
          return;
      }
      setCampaign(updated);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '작업에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading || !campaign) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-white rounded-xl border border-gray-200 h-48" />
        <div className="bg-white rounded-xl border border-gray-200 h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/campaigns')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">
          {error}
        </div>
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
