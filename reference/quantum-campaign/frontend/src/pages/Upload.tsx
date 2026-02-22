import FileUploader from '../components/Upload/FileUploader';
import PreviewTable from '../components/Upload/PreviewTable';
import RegistrationProgress from '../components/Upload/RegistrationProgress';
import { useUpload } from '../hooks/useUpload';
import { downloadTemplate } from '../services/api';

export default function UploadPage() {
  const {
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
  } = useUpload();

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">엑셀 업로드</h1>
        <button
          onClick={downloadTemplate}
          className="px-4 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          양식 다운로드
        </button>
      </div>

      {result && (
        <div
          className={`rounded-lg p-4 text-sm ${
            result.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
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
          {result.skipped && result.skipped.length > 0 && (
            <div className="mt-2 pt-2 border-t border-current/20">
              <div className="font-medium mb-1">건너뛴 항목:</div>
              {result.skipped.map((msg, i) => (
                <div key={i}>- {msg}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 등록 진행 현황 */}
      {(registrationProgress.length > 0 || isRegistering) && (
        <RegistrationProgress
          campaigns={registrationProgress}
          isRegistering={isRegistering}
        />
      )}

      {fileErrors.length > 0 && (
        <div className="bg-red-50 text-red-800 rounded-lg p-4 text-sm">
          {fileErrors.map((e, i) => (
            <div key={i}>{e}</div>
          ))}
        </div>
      )}

      {previews.length === 0 && !result && (
        <FileUploader onSelect={upload} uploading={uploading} />
      )}

      {previews.length > 0 && (
        <PreviewTable
          previews={previews}
          onConfirm={confirm}
          onCancel={reset}
          confirming={confirming}
        />
      )}
    </div>
  );
}
