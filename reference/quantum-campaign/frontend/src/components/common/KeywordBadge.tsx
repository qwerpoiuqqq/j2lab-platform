interface KeywordBadgeProps {
  status: 'normal' | 'warning' | 'critical';
  remaining?: number;
  total?: number;
}

const CONFIG = {
  normal: { emoji: '\uD83D\uDFE2', label: '충분', className: 'bg-green-100 text-green-800' },
  warning: { emoji: '\uD83D\uDFE1', label: '주의', className: 'bg-yellow-100 text-yellow-800' },
  critical: { emoji: '\uD83D\uDD34', label: '부족', className: 'bg-red-100 text-red-800' },
};

export default function KeywordBadge({ status, remaining, total }: KeywordBadgeProps) {
  const cfg = CONFIG[status];
  const showCount = remaining !== undefined && total !== undefined;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.className}`}>
      {cfg.emoji} {cfg.label}
      {showCount && (
        <span className="opacity-75 ml-0.5">{remaining}/{total}</span>
      )}
    </span>
  );
}
