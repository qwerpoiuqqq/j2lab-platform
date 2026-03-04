import logoImage from '@/assets/logo.png';

interface LogicLabLogoProps {
  /** Height in pixels */
  size?: number;
  className?: string;
}

export default function LogicLabLogo({ size = 32, className = '' }: LogicLabLogoProps) {
  return (
    <img
      src={logoImage}
      alt="LOGIC LAB"
      style={{ height: size, width: 'auto' }}
      className={`logo-themed ${className}`}
    />
  );
}
