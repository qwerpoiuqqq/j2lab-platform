import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import type { SuperapAccount } from '@/types';

export default function SuperapAccountsPage() {
  const queryClient = useQueryClient();
  const [editId, setEditId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { data, isLoading: loading } = useQuery({
    queryKey: ['superap-accounts'],
    queryFn: () => campaignAccountsApi.list({ size: 100 }),
  });
  const accounts: SuperapAccount[] = data?.items ?? [];

  const deleteMutation = useMutation({
    mutationFn: (id: number) => campaignAccountsApi.delete(id),
    onSuccess: () => {
      setMessage({ type: 'success', text: '삭제되었습니다.' });
      queryClient.invalidateQueries({ queryKey: ['superap-accounts'] });
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err?.response?.data?.detail || '삭제 실패' });
    },
  });

  const handleDelete = (id: number, userId: string) => {
    if (!confirm(`계정 '${userId}'을(를) 삭제하시겠습니까?`)) return;
    setMessage(null);
    deleteMutation.mutate(id);
  };

  const handleSaved = () => {
    setMessage({ type: 'success', text: '저장되었습니다.' });
    queryClient.invalidateQueries({ queryKey: ['superap-accounts'] });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">계정 관리</h1>
          <p className="mt-1 text-sm text-gray-400">
            superap.io 계정을 관리합니다.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => { setShowCreate(true); setMessage(null); }}
        >
          계정 추가
        </Button>
      </div>

      {message && (
        <div
          className={`rounded-xl p-3 text-sm ${
            message.type === 'success'
              ? 'bg-green-900/20 text-green-400 border border-green-800'
              : 'bg-red-900/20 text-red-400 border border-red-800'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="bg-surface rounded-xl border border-border shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-400">로딩 중...</div>
        ) : accounts.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            등록된 계정이 없습니다. 계정을 추가해주세요.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-raised">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">아이디</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">회사</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">대행사명</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-400 uppercase">트래픽 단가</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-400 uppercase">저장 단가</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">캠페인 수</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">상태</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">등록일</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">작업</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {accounts.map((a) => (
                  <tr key={a.id} className="hover:bg-surface-raised transition-colors">
                    <td className="px-6 py-4 font-medium text-gray-100">{a.user_id_superap}</td>
                    <td className="px-6 py-4 text-gray-400">{a.company_name || '-'}</td>
                    <td className="px-6 py-4 text-gray-400">{a.agency_name || '-'}</td>
                    <td className="px-6 py-4 text-right text-gray-400">{a.unit_cost_traffic}원</td>
                    <td className="px-6 py-4 text-right text-gray-400">{a.unit_cost_save}원</td>
                    <td className="px-6 py-4 text-gray-400">{a.campaign_count}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          a.is_active
                            ? 'bg-green-900/30 text-green-400'
                            : 'bg-surface-raised text-gray-400'
                        }`}
                      >
                        {a.is_active ? '활성' : '비활성'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-400 text-xs">
                      {a.created_at
                        ? new Date(a.created_at).toLocaleDateString('ko-KR')
                        : '-'}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        <button
                          onClick={() => { setEditId(a.id); setMessage(null); }}
                          className="text-sm text-primary-400 hover:text-primary-300 font-medium"
                        >
                          편집
                        </button>
                        <button
                          onClick={() => handleDelete(a.id, a.user_id_superap)}
                          disabled={deleteMutation.isPending}
                          className="text-sm text-red-500 hover:text-red-400 font-medium disabled:opacity-50"
                        >
                          삭제
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreate && (
        <AccountEditModal
          accountId={null}
          onClose={() => setShowCreate(false)}
          onSaved={handleSaved}
        />
      )}

      {editId !== null && (
        <AccountEditModal
          accountId={editId}
          onClose={() => setEditId(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}

// ---- Inline AccountEditModal ----

interface AccountEditModalProps {
  accountId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

function AccountEditModal({ accountId, onClose, onSaved }: AccountEditModalProps) {
  const isCreate = accountId === null;

  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [agencyName, setAgencyName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(isCreate);

  // Load existing account data for edit mode
  const { data: accountsData } = useQuery({
    queryKey: ['superap-accounts'],
    queryFn: () => campaignAccountsApi.list({ size: 100 }),
    enabled: !isCreate,
  });

  // Populate form when data loads (useEffect to avoid setState during render)
  useEffect(() => {
    if (!isCreate && accountsData && !loaded) {
      const acc = accountsData.items.find((a: SuperapAccount) => a.id === accountId);
      if (acc) {
        setUserId(acc.user_id_superap);
        setAgencyName(acc.agency_name || '');
        setLoaded(true);
      }
    }
  }, [isCreate, accountsData, loaded, accountId]);

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
        await campaignAccountsApi.create({
          user_id_superap: userId.trim(),
          password,
          agency_name: agencyName.trim() || undefined,
        });
      } else {
        const data: { password?: string; agency_name?: string; is_active?: boolean } = {
          agency_name: agencyName.trim() || undefined,
        };
        if (password) data.password = password;
        await campaignAccountsApi.update(accountId!, data);
      }
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={isCreate ? '계정 추가' : '계정 편집'}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>취소</Button>
          <Button variant="primary" onClick={handleSave} loading={saving}>
            {isCreate ? '추가' : '저장'}
          </Button>
        </>
      }
    >
      {!loaded && !isCreate ? (
        <div className="text-center py-8 text-gray-400">로딩 중...</div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              아이디 (superap.io 로그인 ID)
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
              placeholder="superap 아이디"
              disabled={!isCreate}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
              placeholder={isCreate ? '비밀번호 입력' : '변경 시에만 입력'}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">대행사명</label>
            <input
              type="text"
              value={agencyName}
              onChange={(e) => setAgencyName(e.target.value)}
              className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
              placeholder="대행사명 (선택)"
            />
          </div>

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>
      )}
    </Modal>
  );
}
