import { useRef } from 'react';

interface FileUploaderProps {
  onSelect: (file: File) => void;
  uploading: boolean;
}

export default function FileUploader({ onSelect, uploading }: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onSelect(file);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
        <div className="text-gray-400 text-4xl mb-3">&#128193;</div>
        <p className="text-sm text-gray-600 mb-4">
          엑셀 파일(.xlsx)을 선택하여 캠페인을 일괄 등록하세요
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          onChange={handleChange}
          className="hidden"
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="px-6 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
        >
          {uploading ? '업로드 중...' : '파일 선택'}
        </button>
      </div>
    </div>
  );
}
