import { useState, useEffect } from 'react';
import CompanyList from '@/components/features/companies/CompanyList';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import { PlusIcon } from '@heroicons/react/24/outline';
import type { Company } from '@/types';

// Mock data
const mockCompanies: Company[] = [
  { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 2, name: '제이투랩', code: 'j2lab', is_active: true, created_at: '2026-01-01T00:00:00Z' },
];

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCode, setNewCode] = useState('');

  useEffect(() => {
    // TODO: Replace with actual API call
    setTimeout(() => {
      setCompanies(mockCompanies);
      setLoading(false);
    }, 300);
  }, []);

  const handleCreate = () => {
    console.log('Create company:', { name: newName, code: newCode });
    setShowCreateModal(false);
    setNewName('');
    setNewCode('');
    // TODO: Call actual API and reload
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

      {/* Table */}
      <CompanyList companies={companies} loading={loading} />

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
            <Button onClick={handleCreate} disabled={!newName || !newCode}>
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
    </div>
  );
}
