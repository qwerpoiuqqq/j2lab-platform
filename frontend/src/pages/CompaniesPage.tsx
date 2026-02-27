import { useState, useEffect } from 'react';
import CompanyList from '@/components/features/companies/CompanyList';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import { PlusIcon } from '@heroicons/react/24/outline';
import type { Company } from '@/types';
import { companiesApi } from '@/api/companies';

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCode, setNewCode] = useState('');
  const [creating, setCreating] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Edit state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [editName, setEditName] = useState('');
  const [editCode, setEditCode] = useState('');
  const [editActive, setEditActive] = useState(true);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    companiesApi
      .list(1, 100)
      .then((data) => {
        if (!cancelled) {
          setCompanies(data.items);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '회사 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      await companiesApi.create({ name: newName, code: newCode });
      setShowCreateModal(false);
      setNewName('');
      setNewCode('');
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '회사 생성에 실패했습니다.');
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = (company: Company) => {
    setEditingCompany(company);
    setEditName(company.name);
    setEditCode(company.code);
    setEditActive(company.is_active);
    setShowEditModal(true);
  };

  const handleEditSubmit = async () => {
    if (!editingCompany) return;
    setEditing(true);
    try {
      await companiesApi.update(editingCompany.id, {
        name: editName,
        is_active: editActive,
      });
      setShowEditModal(false);
      setEditingCompany(null);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '회사 수정에 실패했습니다.');
    } finally {
      setEditing(false);
    }
  };

  const handleDelete = async (company: Company) => {
    if (!confirm(`"${company.name}" 회사를 삭제하시겠습니까?`)) return;
    try {
      await companiesApi.delete(company.id);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '회사 삭제에 실패했습니다.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">회사 관리</h1>
          <p className="mt-1 text-sm text-gray-500">
            회사(테넌트)를 조회하고 관리합니다.
          </p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          icon={<PlusIcon className="h-4 w-4" />}
        >
          회사 생성
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <CompanyList
        companies={companies}
        loading={loading}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      {/* Create Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="회사 생성"
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setShowCreateModal(false)}
            >
              취소
            </Button>
            <Button onClick={handleCreate} disabled={!newName || !newCode} loading={creating}>
              생성
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="회사명"
            placeholder="예: 일류기획"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            required
          />
          <Input
            label="회사 코드"
            placeholder="예: ilryu"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
            helperText="영문 소문자, 고유한 식별 코드"
            required
          />
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title="회사 수정"
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setShowEditModal(false)}
            >
              취소
            </Button>
            <Button onClick={handleEditSubmit} disabled={!editName} loading={editing}>
              수정
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="회사명"
            placeholder="예: 일류기획"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            required
          />
          <Input
            label="회사 코드"
            placeholder="예: ilryu"
            value={editCode}
            onChange={(e) => setEditCode(e.target.value)}
            helperText="회사 코드는 변경할 수 없습니다."
            required
            disabled
          />
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={editActive}
              onChange={(e) => setEditActive(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700">활성 상태</span>
          </label>
        </div>
      </Modal>
    </div>
  );
}
