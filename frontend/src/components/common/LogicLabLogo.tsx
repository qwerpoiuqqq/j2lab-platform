interface LogicLabLogoProps {
  size?: number;
  className?: string;
}

export default function LogicLabLogo({ size = 32, className = '' }: LogicLabLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Circuit brain shape */}
      <rect x="8" y="8" width="48" height="48" rx="12" stroke="currentColor" strokeWidth="2.5" />
      {/* Inner circuit lines */}
      <path
        d="M20 20h8v8h8v-8h8M20 36h8v8h8v-8h8M20 20v24M44 20v24"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Circuit nodes */}
      <circle cx="20" cy="20" r="2.5" fill="currentColor" />
      <circle cx="28" cy="28" r="2.5" fill="currentColor" />
      <circle cx="36" cy="28" r="2.5" fill="currentColor" />
      <circle cx="44" cy="20" r="2.5" fill="currentColor" />
      <circle cx="20" cy="36" r="2.5" fill="currentColor" />
      <circle cx="28" cy="36" r="2.5" fill="currentColor" />
      <circle cx="36" cy="36" r="2.5" fill="currentColor" />
      <circle cx="44" cy="36" r="2.5" fill="currentColor" />
      <circle cx="20" cy="44" r="2.5" fill="currentColor" />
      <circle cx="28" cy="44" r="2.5" fill="currentColor" />
      <circle cx="44" cy="44" r="2.5" fill="currentColor" />
      {/* Center accent */}
      <circle cx="32" cy="32" r="4" fill="currentColor" opacity="0.3" />
      <circle cx="32" cy="32" r="2" fill="currentColor" />
    </svg>
  );
}
