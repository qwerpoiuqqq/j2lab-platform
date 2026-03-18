import type { ReactNode } from 'react';

export const categoryIcons: Record<string, { icon: ReactNode; bg: string; text: string }> = {
  'naver': {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M16.5 4H20V20H16.5L7.5 9.5V20H4V4H7.5L16.5 14.5V4Z" fill="currentColor" />
      </svg>
    ),
    bg: 'bg-emerald-500',
    text: 'text-white',
  },
  'naver-place': {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C8.13 2 5 5.13 5 9C5 14.25 12 22 12 22C12 22 19 14.25 19 9C19 5.13 15.87 2 12 2ZM14.5 12H12.5L9.5 8V12H8V6H10L13 10V6H14.5V12Z" fill="currentColor" />
      </svg>
    ),
    bg: 'bg-emerald-600',
    text: 'text-white',
  },
  'receipt': {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M18 17H6V15H18V17ZM18 13H6V11H18V13ZM18 9H6V7H18V9ZM3 22L4.5 20.5L6 22L7.5 20.5L9 22L10.5 20.5L12 22L13.5 20.5L15 22L16.5 20.5L18 22L19.5 20.5L21 22V2L19.5 3.5L18 2L16.5 3.5L15 2L13.5 3.5L12 2L10.5 3.5L9 2L7.5 3.5L6 2L4.5 3.5L3 2V22Z" fill="currentColor" />
      </svg>
    ),
    bg: 'bg-stone-500',
    text: 'text-white',
  },
  'shopping': {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M16 7V6C16 3.79 14.21 2 12 2C9.79 2 8 3.79 8 6V7H3V20C3 21.1 3.9 22 5 22H19C20.1 22 21 21.1 21 20V7H16ZM10 6C10 4.9 10.9 4 12 4C13.1 4 14 4.9 14 6V7H10V6ZM19 20H5V9H8V11H10V9H14V11H16V9H19V20Z" fill="currentColor" />
      </svg>
    ),
    bg: 'bg-pink-500',
    text: 'text-white',
  },
  'grid': {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 4H10V10H4V4ZM14 4H20V10H14V4ZM4 14H10V20H4V14ZM14 14H20V20H14V14Z" fill="currentColor" />
      </svg>
    ),
    bg: 'bg-slate-600',
    text: 'text-white',
  },
};

export function CategoryIcon({ iconKey, size = 24, className = '' }: { iconKey?: string; size?: number; className?: string }) {
  const entry = categoryIcons[iconKey || 'grid'] || categoryIcons['grid'];

  return (
    <div
      className={`flex items-center justify-center rounded-lg ${entry.bg} ${entry.text} ${className}`}
      style={{ width: size, height: size }}
    >
      <div style={{ width: size * 0.6, height: size * 0.6 }}>
        {entry.icon}
      </div>
    </div>
  );
}
