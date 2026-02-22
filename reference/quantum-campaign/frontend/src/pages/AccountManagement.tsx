import { useState } from 'react';
import { useAccounts } from '../hooks/useAccounts';
import { deleteAccount, getErrorMessage } from '../services/api';
import AccountEditModal from '../components/Account/AccountEditModal';

export default function AccountManagementPage() {
  const { accounts, loading, reload } = useAccounts();
  const [editId, setEditId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleDelete = async (id: number, userId: string) => {
    if (!confirm(`계정 '${userId}'을(를) 삭제하시겠습니까?`)) return;
    setDeleting(id);
    setMessage(null);
    try {
      const result = await deleteAccount(id);
      setMessage({ type: 'success', text: result.message });
      reload();
    } catch (e) {
      setMessage({ type: 'error', text: getErrorMessage(e) });
    } finally {
      setDeleting(null);
    }
  };

  const handleSaved = () => {
    setMessage({ type: 'success', text: '저장되었습니다.' });
    reload();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">계정 관리</h1>
        <button
          onClick={() => { setShowCreate(true); setMessage(null); }}
          className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600"
        >
          계정 추가
        </button>
      </div>

      {message && (
        <div
          className={`rounded-lg p-3 text-sm mb-4 ${
            message.type === 'success'
              ? 'bg-green-50 text-green-800'
              : 'bg-red-50 text-red-800'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">로딩 중...</div>
        ) : accounts.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            등록된 계정이 없습니다. 계정을 추가해주세요.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium">아이디</th>
                <th className="px-4 py-2.5 text-left font-medium">대행사명</th>
                <th className="px-4 py-2.5 text-left font-medium">캠페인 수</th>
                <th className="px-4 py-2.5 text-left font-medium">상태</th>
                <th className="px-4 py-2.5 text-left font-medium">등록일</th>
                <th className="px-4 py-2.5 text-left font-medium">작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {accounts.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{a.user_id}</td>
                  <td className="px-4 py-3 text-gray-600">{a.agency_name || '-'}</td>
                  <td className="px-4 py-3">{a.campaign_count}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        a.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {a.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {a.created_at
                      ? new Date(a.created_at).toLocaleDateString('ko-KR')
                      : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setEditId(a.id); setMessage(null); }}
                        className="text-sm text-blue-500 hover:text-blue-700"
                      >
                        편집
                      </button>
                      <button
                        onClick={() => handleDelete(a.id, a.user_id)}
                        disabled={deleting === a.id}
                        className="text-sm text-red-500 hover:text-red-700 disabled:opacity-50"
                      >
                        {deleting === a.id ? '삭제 중...' : '삭제'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
