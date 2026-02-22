import { useState, type ReactNode } from 'react';

interface FormSectionProps {
  title: string;
  badge?: '필수' | '선택';
  children: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export default function FormSection({
  title,
  badge,
  children,
  collapsible = false,
  defaultOpen = true,
}: FormSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div
        className={`flex items-center justify-between px-4 py-3 bg-gray-50 ${
          collapsible ? 'cursor-pointer select-none' : ''
        }`}
        onClick={collapsible ? () => setOpen((v) => !v) : undefined}
      >
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
          {badge && (
            <span
              className={`text-xs px-1.5 py-0.5 rounded ${
                badge === '필수'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-500'
              }`}
            >
              {badge}
            </span>
          )}
        </div>
        {collapsible && (
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </div>
      {open && <div className="p-4 space-y-4">{children}</div>}
    </div>
  );
}
