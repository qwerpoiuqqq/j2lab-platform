import { useRef, useState } from 'react';
import { ArrowUpTrayIcon } from '@heroicons/react/24/outline';

interface FileUploaderProps {
  onSelect: (file: File) => void;
  uploading: boolean;
}

export default function FileUploader({ onSelect, uploading }: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onSelect(file);
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onSelect(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  return (
    <div className="bg-surface rounded-xl border border-border p-6">
      <div
        className={`border-2 border-dashed rounded-xl p-10 text-center transition-colors ${
          dragOver
            ? 'border-primary-400 bg-primary-50'
            : 'border-border-strong hover:border-gray-400'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setDragOver(false)}
      >
        <ArrowUpTrayIcon className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        <p className="text-sm text-gray-400 mb-1">
          엑셀 파일(.xlsx)을 드래그하거나 선택하여 캠페인을 일괄 등록하세요
        </p>
        <p className="text-xs text-gray-400 mb-4">
          양식을 다운로드하여 양식에 맞게 작성한 파일을 업로드해주세요
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
          className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 text-sm font-medium transition-colors"
        >
          {uploading ? '업로드 중...' : '파일 선택'}
        </button>
      </div>
    </div>
  );
}
