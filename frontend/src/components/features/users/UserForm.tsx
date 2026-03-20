import { useState, useEffect, type FormEvent } from 'react';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import type { CreateUserRequest, Company, UserRole, User } from '@/types';
import { useAuthStore } from '@/store/auth';
import { usersApi } from '@/api/users';

interface UserFormProps {
  companies: Company[];
  onSubmit: (data: CreateUserRequest) => void;
  loading?: boolean;
  onCancel: () => void;
}

const roleOptions: { value: UserRole; label: string }[] = [
  { value: 'company_admin', label: '회사 관리자' },
  { value: 'order_handler', label: '운영자' },
  { value: 'distributor', label: '총판' },
  { value: 'sub_account', label: '하부계정' },
];

const PARENT_ROLE_MAP: Record<string, { parentRole: string; label: string }> = {
  distributor: { parentRole: 'order_handler', label: '상위 담당자' },
  sub_account: { parentRole: 'distributor', label: '상위 총판' },
};

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
  const [parentId, setParentId] = useState<string | undefined>(undefined);
  const [parentCandidates, setParentCandidates] = useState<User[]>([]);
  const [loadingParents, setLoadingParents] = useState(false);

  const availableRoles =
    currentUser?.role === 'system_admin'
      ? roleOptions
      : currentUser?.role === 'company_admin'
        ? roleOptions.filter((r) =>
            ['order_handler', 'distributor', 'sub_account'].includes(r.value),
          )
        : currentUser?.role === 'order_handler'
          ? roleOptions.filter((r) =>
              ['distributor', 'sub_account'].includes(r.value),
            )
          : roleOptions.filter((r) => r.value === 'sub_account');

  // distributor가 sub_account를 생성할 때는 parent_id가 자동으로 자신이 됨
  const parentConfig = PARENT_ROLE_MAP[role];
  const autoAssignedParent =
    currentUser?.role === 'distributor'
    || (currentUser?.role === 'order_handler' && role === 'distributor');
  const needsParent = !!parentConfig && !autoAssignedParent;

  useEffect(() => {
    if (!needsParent) {
      setParentCandidates([]);
      setParentId(undefined);
      return;
    }

    const fetchParents = async () => {
      setLoadingParents(true);
      try {
        const effectiveCompanyId = companyId || currentUser?.company_id;
        const params: { role: string; company_id?: number; size: number } = {
          role: parentConfig.parentRole,
          size: 100,
        };
        if (effectiveCompanyId) {
          params.company_id = effectiveCompanyId;
        }
        const res = await usersApi.list(params);
        setParentCandidates(res.items);
        if (res.items.length > 0 && !res.items.some((u) => u.id === parentId)) {
          setParentId(undefined);
        }
      } catch {
        setParentCandidates([]);
      } finally {
        setLoadingParents(false);
      }
    };

    fetchParents();
  }, [role, companyId]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      email,
      password,
      name,
      phone: phone || undefined,
      company_id: companyId,
      role,
      parent_id: parentId || undefined,
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
        <label className="block text-sm font-medium text-gray-300 mb-1">
          역할 <span className="text-danger-500">*</span>
        </label>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
          className="block w-full rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
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
          <label className="block text-sm font-medium text-gray-300 mb-1">
            소속 회사
          </label>
          <select
            value={companyId || ''}
            onChange={(e) =>
              setCompanyId(e.target.value ? Number(e.target.value) : undefined)
            }
            className="block w-full rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
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

      {needsParent && (
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            {parentConfig.label} <span className="text-danger-500">*</span>
          </label>
          <select
            value={parentId || ''}
            onChange={(e) => setParentId(e.target.value || undefined)}
            className="block w-full rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
            required
            disabled={loadingParents}
          >
            <option value="">
              {loadingParents ? '로딩 중...' : '선택하세요'}
            </option>
            {parentCandidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.email})
              </option>
            ))}
          </select>
          {!loadingParents && parentCandidates.length === 0 && (
            <p className="mt-1 text-xs text-amber-600">
              해당 역할의 상위 유저가 없습니다. 먼저{' '}
              {parentConfig.parentRole === 'order_handler'
                ? '운영자'
                : '총판'}
              를 생성하세요.
            </p>
          )}
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
