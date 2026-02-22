import { useState, useEffect, useRef, useCallback } from 'react';
import type {
  CampaignPreviewItem,
  CampaignConfirmItem,
  ConfirmResponse,
  RegistrationProgressItem,
} from '../types';
import { uploadPreview, confirmUpload, fetchRegistrationProgress } from '../services/api';

export function useUpload() {
  const [previews, setPreviews] = useState<CampaignPreviewItem[]>([]);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<ConfirmResponse | null>(null);

  // 등록 진행 상태 추적
  const [registrationProgress, setRegistrationProgress] = useState<RegistrationProgressItem[]>([]);
  const [isRegistering, setIsRegistering] = useState(false);
  const pollingRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (ids: number[]) => {
      const poll = async () => {
        try {
          const data = await fetchRegistrationProgress(ids);
          setRegistrationProgress(data.campaigns);
          if (data.all_completed) {
            stopPolling();
            setIsRegistering(false);
          }
        } catch {
          // 폴링 실패 시 다음 인터벌에서 재시도
        }
      };
      poll();
      pollingRef.current = window.setInterval(poll, 3000);
    },
    [stopPolling],
  );

  // 컴포넌트 언마운트 시 폴링 정리
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const upload = async (file: File) => {
    setUploading(true);
    setResult(null);
    try {
      const data = await uploadPreview(file);
      setPreviews(data.campaigns);
      setFileErrors(data.file_errors);
    } catch {
      setFileErrors(['파일 업로드에 실패했습니다.']);
    } finally {
      setUploading(false);
    }
  };

  const confirm = async (items: CampaignConfirmItem[]) => {
    setConfirming(true);
    try {
      const res = await confirmUpload(items);
      setResult(res);
      if (res.success) {
        setPreviews([]);
        // 캠페인 ID가 있으면 진행 상태 폴링 시작
        if (res.campaign_ids && res.campaign_ids.length > 0) {
          setIsRegistering(true);
          startPolling(res.campaign_ids);
        }
      }
    } catch {
      setResult({
        success: false,
        message: '등록에 실패했습니다.',
        created_count: 0,
        new_count: 0,
        extend_count: 0,
        skipped: [],
        campaign_ids: [],
      });
    } finally {
      setConfirming(false);
    }
  };

  const reset = () => {
    setPreviews([]);
    setFileErrors([]);
    setResult(null);
    setRegistrationProgress([]);
    setIsRegistering(false);
    stopPolling();
  };

  return {
    previews,
    fileErrors,
    uploading,
    confirming,
    result,
    upload,
    confirm,
    reset,
    registrationProgress,
    isRegistering,
  };
}
