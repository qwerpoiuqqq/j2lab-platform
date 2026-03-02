import { useState, useEffect } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import { PlusIcon, PencilSquareIcon } from '@heroicons/react/24/outline';
import { formatDateTime } from '@/utils/format';
import type { User, CreateUserRequest } from '@/types';
import { usersApi } from '@/api/users';

export default function SubAccountsPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [formData, setFormData] = useState({ name: '', email: '', password: '', phone: '' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    usersApi.list({ role: 'sub_account', size: 100 })
      .then((data) => { if (!cancelled) { setUsers(data.items); setLoading(false); } })
      .catch((err) => { if (!cancelled) { setError(err?.response?.data?.detail || '목록을 불러오지 못했습니다.'); setLoading(false); } });
    return () => { cancelled = true; };
  }, [refreshKey]);

  const openCreate = () => {
    setEditing(null);
    setFormData({ name: '', email: '', password: '', phone: '' });
    setShowModal(true);
  };

  const openEdit = (user: User) => {
    setEditing(user);
    setFormData({ name: user.name, email: user.email, password: '', phone: user.phone || '' });
    setShowModal(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.email) { alert('이름과 이메일을 입력하세요.'); return; }
    if (!editing && !formData.password) { alert('비밀번호를 입력하세요.'); return; }
    setSubmitting(true);
    try {
      if (editing) {
        await usersApi.update(editing.id, {
          name: formData.name,
          phone: formData.phone || undefined,
        });
      } else {
        const payload: CreateUserRequest = {
          name: formData.name,
          email: formData.email,
          password: formData.password,
          phone: formData.phone || undefined,
          role: 'sub_account',
        };
        await usersApi.create(payload);
      }
      setShowModal(false);
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally { setSubmitting(false); }
  };

  const handleToggleActive = async (user: User) => {
    const action = user.is_active ? '비활성화' : '활성화';
    if (!confirm(`'${user.name}' 계정을 ${action}하시겠습니까?`)) return;
    try {
      await usersApi.update(user.id, { is_active: !user.is_active });
      setRefreshKey(k => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || `${action}에 실패했습니다.`);
    }
  };

  const columns: Column<User>[] = [
    { key: 'name', header: '이름', render: (u) => <span className="font-medium text-gray-900">{u.name}</span> },
    { key: 'email', header: '이메일', render: (u) => <span className="text-gray-600 text-sm">{u.email}</span> },
    { key: 'phone', header: '전화번호', render: (u) => <span className="text-gray-600 text-sm">{u.phone || '-'}</span> },
    { key: 'is_active', header: '상태', render: (u) => (
      <Badge variant={u.is_active ? 'success' : 'default'}>{u.is_active ? '활성' : '비활성'}</Badge>
    )},
    { key: 'created_at', header: '생성일', render: (u) => <span className="text-gray-500 text-xs">{formatDateTime(u.created_at)}</span> },
    { key: 'actions' as keyof User, header: '작업', render: (u: User) => (
      <div className="flex items-center gap-1">
        <button onClick={(e) => { e.stopPropagation(); openEdit(u); }} className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors">
          <PencilSquareIcon className="h-4 w-4" />
        </button>
        <button onClick={(e) => { e.stopPropagation(); handleToggleActive(u); }}
          className={`px-2 py-1 text-xs rounded ${u.is_active ? 'text-red-600 hover:bg-red-50' : 'text-green-600 hover:bg-green-50'}`}>
          {u.is_active ? '비활성화' : '활성화'}
        </button>
      </div>
    )},
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">하부계정 관리</h1>
          <p className="mt-1 text-sm text-gray-500">셀러 계정을 관리합니다.</p>
        </div>
        <Button onClick={openCreate} icon={<PlusIcon className="h-4 w-4" />}>계정 추가</Button>
      </div>
      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>}
      <Table<User> columns={columns} data={users} keyExtractor={(u) => u.id} loading={loading} emptyMessage="하부계정이 없습니다." />
      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title={editing ? '계정 수정' : '계정 추가'} size="sm">
        <div className="space-y-4 p-1">
          <Input label="이름" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
          {!editing && (
            <>
              <Input label="이메일" type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} required />
              <Input label="비밀번호" type="password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} required />
            </>
          )}
          <Input label="전화번호" value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowModal(false)}>취소</Button>
            <Button onClick={handleSubmit} loading={submitting}>{editing ? '수정' : '추가'}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
