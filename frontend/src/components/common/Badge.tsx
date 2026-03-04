import type { ReactNode } from 'react';

type BadgeVariant = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-border text-gray-300 ring-1 ring-inset ring-gray-500/10',
  primary: 'bg-primary-900/40 text-primary-300 ring-1 ring-inset ring-primary-400/20',
  success: 'bg-green-900/40 text-green-400 ring-1 ring-inset ring-green-400/20',
  warning: 'bg-yellow-900/40 text-yellow-400 ring-1 ring-inset ring-yellow-400/20',
  danger: 'bg-red-900/40 text-red-400 ring-1 ring-inset ring-red-400/20',
  info: 'bg-blue-900/40 text-blue-300 ring-1 ring-inset ring-blue-400/20',
};

export default function Badge({
  variant = 'default',
  children,
  className = '',
}: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium
        ${variantClasses[variant]}
        ${className}
      `}
    >
      {children}
    </span>
  );
}
