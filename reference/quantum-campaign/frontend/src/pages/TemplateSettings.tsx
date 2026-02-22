import { useState } from 'react';
import { useTemplates, useModules } from '../hooks/useTemplates';
import { deleteTemplate, getErrorMessage } from '../services/api';
import TemplateEditModal from '../components/Template/TemplateEditModal';
import EmptyState from '../components/common/EmptyState';

export default function TemplateSettingsPage() {
  const { templates, loading, reload } = useTemplates();
  const { modules } = useModules();
  const [editId, setEditId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleDelete = async (id: number, typeName: string) => {
    if (!confirm(`템플릿 '${typeName}'을(를) 삭제하시겠습니까?`)) return;
    setDeleting(id);
    setMessage(null);
    try {
      const result = await deleteTemplate(id);
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

  const openCreate = () => {
    setShowCreate(true);
    setMessage(null);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">템플릿 관리</h1>
          {templates.length > 0 && (
            <p className="text-sm text-gray-500 mt-0.5">
              엑셀 업로드 시 캠페인타입 열에 매칭되는 템플릿 {templates.length}개
            </p>
          )}
        </div>
        <button
          onClick={openCreate}
          className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 flex items-center gap-1.5"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          템플릿 추가
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
        ) : templates.length === 0 ? (
          <EmptyState
            title="등록된 템플릿이 없습니다"
            description="템플릿을 생성하여 캠페인 자동화를 시작하세요. 템플릿은 엑셀 업로드 시 캠페인 타입과 매칭됩니다."
            actionLabel="첫 템플릿 만들기"
            onAction={openCreate}
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium">캠페인 이름</th>
                <th className="px-4 py-2.5 text-left font-medium">캠페인 타입</th>
                <th className="px-4 py-2.5 text-left font-medium">모듈</th>
                <th className="px-4 py-2.5 text-left font-medium">상태</th>
                <th className="px-4 py-2.5 text-left font-medium">작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {templates.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{t.type_name}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {t.campaign_type_selection || '-'}
                  </td>
                  <td className="px-4 py-3">
                    {t.module_descriptions.length > 0
                      ? t.module_descriptions.join(', ')
                      : <span className="text-gray-400">-</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        t.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {t.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setEditId(t.id); setMessage(null); }}
                        className="text-sm text-blue-500 hover:text-blue-700"
                      >
                        편집
                      </button>
                      <button
                        onClick={() => handleDelete(t.id, t.type_name)}
                        disabled={deleting === t.id}
                        className="text-sm text-red-500 hover:text-red-700 disabled:opacity-50"
                      >
                        {deleting === t.id ? '삭제 중...' : '삭제'}
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
        <TemplateEditModal
          templateId={null}
          modules={modules}
          onClose={() => setShowCreate(false)}
          onSaved={handleSaved}
        />
      )}

      {editId !== null && (
        <TemplateEditModal
          templateId={editId}
          modules={modules}
          onClose={() => setEditId(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
