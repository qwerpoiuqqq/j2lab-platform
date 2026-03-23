interface LoginToggleProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export default function LoginToggle({ label, checked, onChange }: LoginToggleProps) {
  return (
    <label className="inline-flex items-center gap-3 cursor-pointer select-none">
      <span className="text-sm text-[#4e5968]">{label}</span>
      {/* 시각적 토글 */}
      <div
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); onChange(!checked); } }}
        tabIndex={0}
        className={`
          relative w-11 h-6 rounded-full cursor-pointer
          transition-colors duration-200 ease-out
          focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3182f6] focus-visible:ring-offset-2
          ${checked ? 'bg-[#3182f6]' : 'bg-[#e5e8eb]'}
        `}
      >
        {/* 썸 (흰 원) */}
        <div
          className={`
            absolute top-[2px] left-[2px]
            w-5 h-5 rounded-full bg-white shadow-sm
            transition-transform duration-200 ease-out
            ${checked ? 'translate-x-5' : 'translate-x-0'}
          `}
        />
      </div>
    </label>
  );
}
