import { useState, useEffect, useMemo } from 'react';
import Button from '@/components/common/Button';
import Badge from '@/components/common/Badge';
import Modal from '@/components/common/Modal';
import { formatCurrency } from '@/utils/format';
import { pricesApi } from '@/api/prices';
import { categoriesApi } from '@/api/categories';
import type { Category } from '@/types';

// ---------------------------------------------------------------------------
// Types for this page
// ---------------------------------------------------------------------------

interface MatrixUser {
  id: string;
  name: string;
  role: string;
  email: string;
}

interface MatrixProduct {
  id: number;
  name: string;
  code: string;
  category?: string;
  base_price: number;
}

// ---------------------------------------------------------------------------
// Inline: UserCard
// ---------------------------------------------------------------------------

function UserCard({
  user,
  priceCount,
  onConfigure,
}: {
  user: MatrixUser;
  priceCount: number;
  onConfigure: () => void;
}) {
  const roleColors: Record<string, string> = {
    distributor: 'bg-blue-500',
    sub_account: 'bg-green-500',
  };
  const roleLabels: Record<string, string> = {
    distributor: '총판',
    sub_account: '셀러',
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:shadow-md transition-shadow">
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-10 h-10 rounded-full ${roleColors[user.role] || 'bg-gray-500'} flex items-center justify-center text-white font-bold text-sm`}
        >
          {user.name.charAt(0)}
        </div>
        <div>
          <h3 className="font-semibold text-gray-900">{user.name}</h3>
          <Badge variant={user.role === 'distributor' ? 'primary' : 'success'}>
            {roleLabels[user.role] || user.role}
          </Badge>
        </div>
      </div>
      <p className="text-sm text-gray-500 mb-1">{user.email}</p>
      <p className="text-sm text-gray-500 mb-3">
        {priceCount > 0 ? `${priceCount}개 개별 단가 설정됨` : '기본 단가 적용 중'}
      </p>
      <Button size="sm" variant="secondary" onClick={onConfigure} className="w-full">
        설정하기
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function PriceMatrixPage() {
  // ---- data states ----
  const [matrixUsers, setMatrixUsers] = useState<MatrixUser[]>([]);
  const [matrixProducts, setMatrixProducts] = useState<MatrixProduct[]>([]);
  const [matrixPrices, setMatrixPrices] = useState<Record<string, Record<number, number>>>({});
  const [categories, setCategories] = useState<Category[]>([]);

  // ---- UI states ----
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---- Modal states ----
  const [selectedUser, setSelectedUser] = useState<MatrixUser | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('__all__');
  const [editedPrices, setEditedPrices] = useState<Record<number, number>>({});
  const [saving, setSaving] = useState(false);

  // ---- Initial data fetch ----
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      pricesApi.getUserMatrix(),
      categoriesApi.list({ size: 200 }),
    ])
      .then(([matrixRes, categoriesRes]) => {
        if (cancelled) return;
        setMatrixUsers(matrixRes.users);
        setMatrixProducts(matrixRes.products);
        setMatrixPrices(matrixRes.prices);
        setCategories(categoriesRes.items);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || '데이터를 불러오지 못했습니다.');
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // ---- Per-user custom price counts (differs from base_price) ----
  const priceCounts = useMemo(() => {
    const baseMap = new Map(matrixProducts.map((p) => [p.id, p.base_price]));
    const counts: Record<string, number> = {};
    for (const [userId, prices] of Object.entries(matrixPrices)) {
      let custom = 0;
      for (const [pidStr, price] of Object.entries(prices)) {
        const base = baseMap.get(parseInt(pidStr)) || 0;
        if (price !== base) custom++;
      }
      counts[userId] = custom;
    }
    return counts;
  }, [matrixPrices, matrixProducts]);

  // ---- Open modal for a user ----
  const handleConfigure = (user: MatrixUser) => {
    setSelectedUser(user);
    setModalOpen(true);
    setEditedPrices({});
    setSelectedCategory('__all__');
  };

  // ---- Current user's prices (from matrix data, no extra API call) ----
  const currentUserPrices = useMemo(() => {
    if (!selectedUser) return {};
    return matrixPrices[selectedUser.id] || {};
  }, [selectedUser, matrixPrices]);

  // ---- Close modal ----
  const handleCloseModal = () => {
    setModalOpen(false);
    setSelectedUser(null);
    setEditedPrices({});
  };

  // ---- Save prices ----
  const handleSave = async () => {
    if (!selectedUser) return;
    setSaving(true);
    try {
      const entries = Object.entries(editedPrices);
      for (const [prodIdStr, price] of entries) {
        const productId = parseInt(prodIdStr);
        await pricesApi.updatePrice(productId, {
          user_id: selectedUser.id,
          price,
        });
      }

      // Update local state — merge edited prices into existing
      setMatrixPrices((prev) => ({
        ...prev,
        [selectedUser.id]: { ...(prev[selectedUser.id] || {}), ...editedPrices },
      }));

      setEditedPrices({});
      handleCloseModal();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  // ---- Filtered products for modal ----
  const filteredProducts = useMemo(() => {
    if (!selectedCategory || selectedCategory === '__all__') return matrixProducts;
    return matrixProducts.filter((p) => p.category === selectedCategory);
  }, [matrixProducts, selectedCategory]);

  // ---- Has changes? ----
  const hasChanges = Object.keys(editedPrices).length > 0;

  // =========================================================================
  // RENDER
  // =========================================================================

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">단가 설정</h1>
          <p className="mt-1 text-sm text-gray-500">총판/셀러별 상품 단가를 관리합니다.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="animate-pulse bg-gray-200 rounded-xl h-40" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">단가 설정</h1>
        <p className="mt-1 text-sm text-gray-500">
          총판/셀러별 상품 단가를 개별적으로 설정합니다.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* User Cards Grid */}
      {matrixUsers.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500 text-sm">
          등록된 총판/셀러가 없습니다.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {matrixUsers.map((user) => (
            <UserCard
              key={user.id}
              user={user}
              priceCount={priceCounts[user.id] || 0}
              onConfigure={() => handleConfigure(user)}
            />
          ))}
        </div>
      )}

      {/* Price Settings Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={handleCloseModal}
        title={selectedUser ? `${selectedUser.name}님의 단가 설정` : '단가 설정'}
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={handleCloseModal}>
              취소
            </Button>
            <Button onClick={handleSave} loading={saving} disabled={!hasChanges}>
              저장
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {/* Category Tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedCategory('__all__')}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                selectedCategory === '__all__'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              전체
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.name)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  selectedCategory === cat.name
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* Product price rows */}
          {filteredProducts.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              해당 카테고리에 상품이 없습니다.
            </div>
          ) : (
            <div className="space-y-2">
              {filteredProducts.map((product) => {
                const effectivePrice = currentUserPrices[product.id] ?? product.base_price;
                const currentPrice = editedPrices[product.id] ?? effectivePrice;
                const discountRate =
                  product.base_price > 0
                    ? Math.round((1 - currentPrice / product.base_price) * 100)
                    : 0;
                const isCustom = currentPrice !== product.base_price;

                return (
                  <div
                    key={product.id}
                    className={`flex items-center gap-3 p-3 rounded-lg ${isCustom ? 'bg-blue-50' : 'bg-gray-50'}`}
                  >
                    <span className="flex-1 text-sm font-medium text-gray-900">
                      {product.name}
                    </span>
                    <span className="text-xs text-gray-400 bg-gray-200 px-2 py-1 rounded">
                      기본 {formatCurrency(product.base_price)}
                    </span>
                    <input
                      type="number"
                      value={currentPrice}
                      onChange={(e) =>
                        setEditedPrices((prev) => ({
                          ...prev,
                          [product.id]: parseInt(e.target.value) || 0,
                        }))
                      }
                      className="w-32 px-3 py-2 text-right text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    {discountRate > 0 && (
                      <span className="text-xs text-red-500 font-medium min-w-[60px]">
                        {discountRate}% 할인
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
