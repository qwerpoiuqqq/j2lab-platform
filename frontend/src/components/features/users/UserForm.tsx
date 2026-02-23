import { useState, type FormEvent } from 'react';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import type { CreateUserRequest, Company, UserRole } from '@/types';
import { useAuthStore } from '@/store/auth';

interface UserFormProps {
  companies: Company[];
  onSubmit: (data: CreateUserRequest) => void;
  loading?: boolean;
  onCancel: () => void;
}

const roleOptions: { value: UserRole; label: string }[] = [
  { value: 'company_admin', label: '회사 관리자' },
  { value: 'order_handler', label: '접수 담당자' },
  { value: 'distributor', label: '총판' },
  { value: 'sub_account', label: '하부계정' },
];

export default function UserForm({ companies, onSubmit, loading, onCancel }: UserFormProps) {
  const currentUser = useAuthStore((s) => s.user);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState<UserRole>('sub_account');
  const [companyId, setCompanyId] = useState<number | undefined>(
    currentUser?.company_id || undefined,
  );

  const availableRoles =
    currentUser?.role === 'system_admin'
      ? [{ value: 'system_admin' as UserRole, label: '시스템 관리자' }, ...roleOptions]
      : currentUser?.role === 'company_admin'
        ? roleOptions.filter((r) =>
            ['order_handler', 'distributor', 'sub_account'].includes(r.value),
          )
        : roleOptions.filter((r) => r.value === 'sub_account');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      email,
      password,
      name,
      phone: phone || undefined,
      company_id: companyId,
      role,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="이름"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        placeholder="홍길동"
      />
      <Input
        label="이메일"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        placeholder="user@example.com"
      />
      <Input
        label="비밀번호"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        placeholder="8자 이상"
        helperText="최소 8자 이상의 비밀번호를 입력하세요."
      />
      <Input
        label="전화번호"
        type="tel"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        placeholder="010-0000-0000"
      />

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          역할 <span className="text-danger-500">*</span>
        </label>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
          className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          required
        >
          {availableRoles.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      {currentUser?.role === 'system_admin' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            소속 회사
          </label>
          <select
            value={companyId || ''}
            onChange={(e) =>
              setCompanyId(e.target.value ? Number(e.target.value) : undefined)
            }
            className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">선택 안함 (시스템 관리자)</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex justify-end gap-3 pt-4">
        <Button type="button" variant="secondary" onClick={onCancel}>
          취소
        </Button>
        <Button type="submit" loading={loading}>
          생성
        </Button>
      </div>
    </form>
  );
}
