import { useState, useEffect, useMemo } from 'react';
import Button from '@/components/common/Button';
import Badge from '@/components/common/Badge';
import Modal from '@/components/common/Modal';
import { formatCurrency } from '@/utils/format';
import { pricesApi } from '@/api/prices';
import { usersApi } from '@/api/users';
import { productsApi } from '@/api/products';
import { categoriesApi } from '@/api/categories';
import type { User, Product, Category } from '@/types';

// ---------------------------------------------------------------------------
// Inline: UserCard
// ---------------------------------------------------------------------------

function UserCard({
  user,
  priceCount,
  onConfigure,
}: {
  user: User;
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
      <p className="text-sm text-gray-500 mb-3">
        {priceCount > 0 ? `${priceCount}개 설정됨` : '미설정'}
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
  const [users, setUsers] = useState<User[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [priceCounts, setPriceCounts] = useState<Record<string, number>>({});

  // ---- UI states ----
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---- Modal states ----
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [userPrices, setUserPrices] = useState<Record<number, number>>({});
  const [editedPrices, setEditedPrices] = useState<Record<number, number>>({});
  const [modalLoading, setModalLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // ---- Initial data fetch ----
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      usersApi.list({ size: 200 }),
      productsApi.list({ size: 200, is_active: true }),
      categoriesApi.list({ size: 200, is_active: true }),
      pricesApi.getMatrix(),
    ])
      .then(([usersRes, productsRes, categoriesRes, matrixRes]) => {
        if (cancelled) return;

        const filteredUsers = usersRes.items.filter(
          (u) => u.is_active && (u.role === 'distributor' || u.role === 'sub_account'),
        );
        setUsers(filteredUsers);
        setProducts(productsRes.items);
        setCategories(categoriesRes.items);

        // Compute per-user price counts from matrix
        const counts: Record<string, number> = {};
        for (const row of matrixRes.rows) {
          for (const [userId, price] of Object.entries(row.prices)) {
            if (price && price > 0) {
              counts[userId] = (counts[userId] || 0) + 1;
            }
          }
        }
        setPriceCounts(counts);
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

  // ---- Open modal for a user ----
  const handleConfigure = async (user: User) => {
    setSelectedUser(user);
    setModalOpen(true);
    setModalLoading(true);
    setEditedPrices({});

    // Default to first category
    if (categories.length > 0 && !selectedCategory) {
      setSelectedCategory(categories[0].name);
    }

    try {
      const prices = await pricesApi.getUserPrices(user.id);
      setUserPrices(prices);
    } catch {
      setUserPrices({});
    } finally {
      setModalLoading(false);
    }
  };

  // ---- Close modal ----
  const handleCloseModal = () => {
    setModalOpen(false);
    setSelectedUser(null);
    setUserPrices({});
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

      // Update local price counts
      const newUserPrices = { ...userPrices, ...editedPrices };
      const count = Object.values(newUserPrices).filter((p) => p > 0).length;
      setPriceCounts((prev) => ({ ...prev, [selectedUser.id]: count }));
      setUserPrices(newUserPrices);
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
    if (!selectedCategory) return products;
    return products.filter((p) => p.category === selectedCategory);
  }, [products, selectedCategory]);

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
      {users.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500 text-sm">
          등록된 총판/셀러가 없습니다.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {users.map((user) => (
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
        {modalLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse h-12 bg-gray-200 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Category Tabs */}
            {categories.length > 0 && (
              <div className="flex flex-wrap gap-2">
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
            )}

            {/* Product price rows */}
            {filteredProducts.length === 0 ? (
              <div className="text-center py-8 text-gray-400 text-sm">
                해당 카테고리에 상품이 없습니다.
              </div>
            ) : (
              <div className="space-y-2">
                {filteredProducts.map((product) => {
                  const currentPrice =
                    editedPrices[product.id] ?? userPrices[product.id] ?? product.base_price;
                  const discountRate =
                    product.base_price > 0
                      ? Math.round((1 - currentPrice / product.base_price) * 100)
                      : 0;

                  return (
                    <div
                      key={product.id}
                      className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
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
        )}
      </Modal>
    </div>
  );
}
