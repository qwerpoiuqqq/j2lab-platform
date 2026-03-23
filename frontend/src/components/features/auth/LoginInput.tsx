import { type InputHTMLAttributes, useId } from 'react';

interface LoginInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string;
  error?: boolean;
}

export default function LoginInput({ label, error = false, className = '', ...props }: LoginInputProps) {
  const id = useId();

  return (
    <div className="space-y-1.5">
      <label
        htmlFor={id}
        className={`
          block text-[13px] font-semibold
          ${error ? 'text-[#f04452]' : 'text-[#4e5968]'}
        `}
      >
        {label}
      </label>
      <input
        id={id}
        placeholder={`${label}을 입력해 주세요`}
        aria-invalid={error || undefined}
        className={`
          w-full
          bg-[#f7f8fa]
          rounded-xl
          px-4 py-3.5
          outline-none
          text-[15px]
          text-[#191f28]
          placeholder:text-[#adb5bd]
          caret-[#3182f6]
          border
          transition-all duration-200
          ${error
            ? 'border-[#f04452] focus:border-[#f04452] focus:ring-2 focus:ring-[#f04452]/20'
            : 'border-[#e5e8eb] hover:border-[#d1d6db] focus:border-[#3182f6] focus:ring-2 focus:ring-[#3182f6]/20'
          }
          [&:-webkit-autofill]:bg-[#f7f8fa]
          [&:-webkit-autofill]:[transition:background-color_9999s_ease-in-out_0s]
          ${className}
        `}
        {...props}
      />
    </div>
  );
}
