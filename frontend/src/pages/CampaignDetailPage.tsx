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

  // eslint warns about loadCampaign not in deps, but loadCampaign references `id` from closure.
  // Including loadCampaign would cause infinite loop since it's redefined every render.
  // Using `id` as dep is the correct behavior: re-fetch when id changes.
  useEffect(() => {
    loadCampaign();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleAction = async (action: string) => {
    if (!id) return;
    setActionLoading(true);
    try {
      switch (action) {
        case 'pause': {
          const updated = await campaignsApi.pause(Number(id));
          setCampaign(updated);
          break;
        }
        case 'resume': {
          const updated = await campaignsApi.resume(Number(id));
          setCampaign(updated);
          break;
        }
        case 'rotate':
          await campaignsApi.rotateKeywords(Number(id));
          await loadCampaign();
          break;
        default:
          setActionLoading(false);
          return;
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || '작업에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

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
