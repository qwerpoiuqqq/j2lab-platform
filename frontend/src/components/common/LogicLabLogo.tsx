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
      {/* Circuit Brain Logo — left hemisphere traces */}
      <path d="M30 5 C24 3, 16 6, 11 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M29 11 C22 9, 13 13, 9 21" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M29 17 C21 17, 11 21, 9 29" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M29 24 C21 24, 13 28, 13 36" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M30 32 C24 32, 18 36, 19 42" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M31 39 C28 40, 24 44, 27 48" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />

      {/* Right hemisphere traces */}
      <path d="M34 5 C40 3, 48 6, 53 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M35 11 C42 9, 51 13, 55 21" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M35 17 C43 17, 53 21, 55 29" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M35 24 C43 24, 51 28, 51 36" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M34 32 C40 32, 46 36, 45 42" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M33 39 C36 40, 40 44, 37 48" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />

      {/* Center bridges */}
      <line x1="29" y1="11" x2="35" y2="11" stroke="currentColor" strokeWidth="1.4" />
      <line x1="29" y1="17" x2="35" y2="17" stroke="currentColor" strokeWidth="1.4" />
      <line x1="29" y1="24" x2="35" y2="24" stroke="currentColor" strokeWidth="1.4" />
      <line x1="30" y1="32" x2="34" y2="32" stroke="currentColor" strokeWidth="1.4" />
      <line x1="31" y1="39" x2="33" y2="39" stroke="currentColor" strokeWidth="1.4" />

      {/* Stem */}
      <path d="M32 48 L32 59" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M32 55 L28 58" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M32 57 L36 60" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />

      {/* Nodes — left endpoints */}
      <circle cx="11" cy="13" r="2" fill="currentColor" />
      <circle cx="9" cy="21" r="2" fill="currentColor" />
      <circle cx="9" cy="29" r="2" fill="currentColor" />
      <circle cx="13" cy="36" r="2" fill="currentColor" />
      <circle cx="19" cy="42" r="2" fill="currentColor" />
      <circle cx="27" cy="48" r="1.8" fill="currentColor" />

      {/* Nodes — right endpoints */}
      <circle cx="53" cy="13" r="2" fill="currentColor" />
      <circle cx="55" cy="21" r="2" fill="currentColor" />
      <circle cx="55" cy="29" r="2" fill="currentColor" />
      <circle cx="51" cy="36" r="2" fill="currentColor" />
      <circle cx="45" cy="42" r="2" fill="currentColor" />
      <circle cx="37" cy="48" r="1.8" fill="currentColor" />

      {/* Nodes — mid-curve left */}
      <circle cx="19" cy="7" r="1.5" fill="currentColor" />
      <circle cx="15" cy="15" r="1.5" fill="currentColor" />
      <circle cx="14" cy="23" r="1.5" fill="currentColor" />
      <circle cx="17" cy="30" r="1.5" fill="currentColor" />
      <circle cx="22" cy="38" r="1.5" fill="currentColor" />

      {/* Nodes — mid-curve right */}
      <circle cx="45" cy="7" r="1.5" fill="currentColor" />
      <circle cx="49" cy="15" r="1.5" fill="currentColor" />
      <circle cx="50" cy="23" r="1.5" fill="currentColor" />
      <circle cx="47" cy="30" r="1.5" fill="currentColor" />
      <circle cx="42" cy="38" r="1.5" fill="currentColor" />

      {/* Nodes — top & center */}
      <circle cx="30" cy="5" r="1.8" fill="currentColor" />
      <circle cx="34" cy="5" r="1.8" fill="currentColor" />
      <circle cx="32" cy="11" r="1.5" fill="currentColor" />
      <circle cx="32" cy="17" r="1.5" fill="currentColor" />
      <circle cx="32" cy="24" r="1.5" fill="currentColor" />
      <circle cx="32" cy="32" r="1.5" fill="currentColor" />
      <circle cx="32" cy="39" r="1.5" fill="currentColor" />

      {/* Nodes — stem */}
      <circle cx="32" cy="48" r="1.8" fill="currentColor" />
      <circle cx="32" cy="59" r="2" fill="currentColor" />
      <circle cx="28" cy="58" r="1.5" fill="currentColor" />
      <circle cx="36" cy="60" r="1.5" fill="currentColor" />
    </svg>
  );
}
