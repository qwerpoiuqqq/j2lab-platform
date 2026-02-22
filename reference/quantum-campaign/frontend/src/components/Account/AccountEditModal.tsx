import { useEffect, useState } from 'react';
import Modal from '../common/Modal';
import { createAccount, updateAccount, fetchAccounts, getErrorMessage } from '../../services/api';
import type { Account, AccountCreate, AccountUpdate } from '../../types';

interface AccountEditModalProps {
  accountId: number | null; // null = 생성 모드
  onClose: () => void;
  onSaved: () => void;
}

export default function AccountEditModal({
  accountId,
  onClose,
  onSaved,
}: AccountEditModalProps) {
  const isCreate = accountId === null;

  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [agencyName, setAgencyName] = useState('');
  const [loading, setLoading] = useState(!isCreate);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isCreate) return;
    fetchAccounts()
      .then((data) => {
        const account = data.accounts.find((a: Account) => a.id === accountId);
        if (account) {
          setUserId(account.user_id);
          setAgencyName(account.agency_name || '');
        } else {
          setError('계정을 찾을 수 없습니다.');
        }
      })
      .catch(() => setError('계정 정보를 불러올 수 없습니다.'))
      .finally(() => setLoading(false));
  }, [accountId, isCreate]);

  const handleSave = async () => {
    if (!userId.trim()) {
      setError('아이디를 입력해주세요.');
      return;
    }
    if (isCreate && !password) {
      setError('비밀번호를 입력해주세요.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (isCreate) {
        const data: AccountCreate = {
          user_id: userId.trim(),
          password,
          agency_name: agencyName.trim() || undefined,
        };
        await createAccount(data);
      } else {
        const data: AccountUpdate = {
          user_id: userId.trim(),
          agency_name: agencyName.trim(),
        };
        if (password) data.password = password;
        await updateAccount(accountId, data);
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={isCreate ? '계정 추가' : '계정 편집'}>
      {loading ? (
        <div className="text-center py-8 text-gray-500">로딩 중...</div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              아이디 (superap.io 로그인 ID)
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="superap 아이디"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              비밀번호
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder={isCreate ? '비밀번호 입력' : '변경 시에만 입력'}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              대행사명
            </label>
            <input
              type="text"
              value={agencyName}
              onChange={(e) => setAgencyName(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="대행사명 (선택)"
            />
          </div>

          {error && <div className="text-sm text-red-600">{error}</div>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
            >
              {saving ? '저장 중...' : isCreate ? '추가' : '저장'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
