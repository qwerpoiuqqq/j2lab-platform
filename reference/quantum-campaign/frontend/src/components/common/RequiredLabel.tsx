import type { ReactNode } from 'react';

interface RequiredLabelProps {
  children: ReactNode;
  required?: boolean;
}

export default function RequiredLabel({ children, required }: RequiredLabelProps) {
  return (
    <label className="block text-sm font-medium text-gray-700 mb-1">
      {children}
      {required && <span className="text-red-500 ml-0.5">*</span>}
    </label>
  );
}
