import { useState, useEffect, useCallback, useRef } from 'react';
import { campaignUploadApi } from '@/api/campaignUpload';
import { downloadBlob } from '@/utils/format';
import Button from '@/components/common/Button';
import FileUploader from '@/components/features/campaigns/FileUploader';
import PreviewTable from '@/components/features/campaigns/PreviewTable';
import RegistrationProgress from '@/components/features/campaigns/RegistrationProgress';
import type { CampaignUploadPreviewItem, RegistrationProgressItem } from '@/types';

export default function CampaignUploadPage() {
  const [previews, setPreviews] = useState<CampaignUploadPreviewItem[]>([]);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [registrationProgress, setRegistrationProgress] = useState<RegistrationProgressItem[]>([]);
  const [isRegistering, setIsRegistering] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const reset = () => {
    setPreviews([]);
    setFileErrors([]);
    setResult(null);
    setRegistrationProgress([]);
    setIsRegistering(false);
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setFileErrors([]);
    setPreviews([]);
    setResult(null);
    try {
      const res = await campaignUploadApi.preview(file);
      setPreviews(res.items);
      if (res.error_count > 0) {
        setFileErrors([`${res.error_count}건의 오류가 발견되었습니다. 오류 행은 선택할 수 없습니다.`]);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') {
        setFileErrors([detail]);
      } else if (Array.isArray(detail)) {
        setFileErrors(detail.map((d: any) => typeof d === 'string' ? d : d.msg || JSON.stringify(d)));
      } else {
        setFileErrors(['파일 처리에 실패했습니다.']);
      }
    } finally {
      setUploading(false);
    }
  };

  const startPolling = useCallback(() => {
    setIsRegistering(true);
    const poll = async () => {
      try {
        const res = await campaignUploadApi.getProgress();
        setRegistrationProgress(res.items);
        const allDone = res.items.every(
          (c) => c.registration_step === 'completed' || c.registration_step === 'failed',
        );
        if (allDone && res.items.length > 0) {
          setIsRegistering(false);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          const completed = res.items.filter((c) => c.registration_step === 'completed').length;
          const failed = res.items.filter((c) => c.registration_step === 'failed').length;
          setResult({
            success: failed === 0,
            message: `등록 완료: ${completed}건 성공${failed > 0 ? `, ${failed}건 실패` : ''}`,
          });
        }
      } catch {
        // polling error, continue
      }
    };
    poll();
    pollRef.current = setInterval(poll, 3000);
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleConfirm = async (rowNumbers: number[]) => {
    setConfirming(true);
    setResult(null);
    try {
      const selectedItems = previews
        .filter((p) => rowNumbers.includes(p.row_number) && p.is_valid)
        .map((p) => ({
          place_url: p.place_url,
          place_name: p.place_name,
          campaign_type: p.campaign_type,
          start_date: p.start_date,
          end_date: p.end_date,
          daily_limit: p.daily_limit,
          keywords: p.keywords,
          agency_name: p.agency_name,
          account_user_id: p.user_id,
        }));
      const res = await campaignUploadApi.confirm({ items: selectedItems });
      setPreviews([]);
      setResult({ success: true, message: res.message });
      startPolling();
    } catch (err: any) {
      setResult({
        success: false,
        message: err?.response?.data?.detail || '등록에 실패했습니다.',
      });
    } finally {
      setConfirming(false);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await campaignUploadApi.downloadTemplate();
      downloadBlob(blob, 'campaign_template.xlsx');
    } catch {
      alert('양식 다운로드에 실패했습니다.');
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">엑셀 업로드</h1>
          <p className="mt-1 text-sm text-gray-500">
            엑셀 파일로 캠페인을 일괄 등록합니다.
          </p>
        </div>
        <Button variant="secondary" onClick={handleDownloadTemplate}>
          양식 다운로드
        </Button>
      </div>

      {/* Result message */}
      {result && (
        <div
          className={`rounded-xl p-4 text-sm ${
            result.success ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          <div>
            {result.message}
            {result.success && !isRegistering && (
              <button
                onClick={reset}
                className="ml-4 underline hover:no-underline"
              >
                새로 업로드
              </button>
            )}
          </div>
        </div>
      )}

      {/* Registration progress */}
      {(registrationProgress.length > 0 || isRegistering) && (
        <RegistrationProgress
          campaigns={registrationProgress}
          isRegistering={isRegistering}
        />
      )}

      {/* File errors */}
      {fileErrors.length > 0 && (
        <div className="bg-red-50 text-red-800 rounded-xl p-4 text-sm border border-red-200">
          {fileErrors.map((e, i) => (
            <div key={i}>{e}</div>
          ))}
        </div>
      )}

      {/* File uploader */}
      {previews.length === 0 && !result && (
        <FileUploader onSelect={handleUpload} uploading={uploading} />
      )}

      {/* Preview table */}
      {previews.length > 0 && (
        <PreviewTable
          previews={previews}
          onConfirm={handleConfirm}
          onCancel={reset}
          confirming={confirming}
        />
      )}
    </div>
  );
}
