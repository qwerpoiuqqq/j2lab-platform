import { useState, useEffect } from 'react';
import Button from '@/components/common/Button';
import { formatCurrency } from '@/utils/format';
import { pricesApi } from '@/api/prices';
import type { PriceMatrixRow } from '@/types';

interface Seller {
  id: string;
  name: string;
}

export default function PriceMatrixPage() {
  const [rows, setRows] = useState<PriceMatrixRow[]>([]);
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingCell, setEditingCell] = useState<{ productId: number; sellerId: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    pricesApi
      .getMatrix()
      .then((data) => {
        if (!cancelled) {
          setRows(data.rows);
          setSellers(data.sellers);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '가격 매트릭스를 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, []);

  const handleCellClick = (productId: number, sellerId: string, currentPrice: number) => {
    setEditingCell({ productId, sellerId });
    setEditValue(String(currentPrice || ''));
  };

  const handleSave = async () => {
    if (!editingCell) return;
    setSaving(true);
    try {
      const price = parseInt(editValue) || 0;
      await pricesApi.updatePrice(editingCell.productId, {
        role: editingCell.sellerId,
        price,
      });

      setRows((prev) =>
        prev.map((row) => {
          if (row.product_id === editingCell.productId) {
            return {
              ...row,
              prices: { ...row.prices, [editingCell.sellerId]: price },
            };
          }
          return row;
        }),
      );
      setEditingCell(null);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave();
    if (e.key === 'Escape') setEditingCell(null);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">가격 매트릭스</h1>
          <p className="mt-1 text-sm text-gray-500">상품별 판매자 가격을 관리합니다.</p>
        </div>
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">가격 매트릭스</h1>
        <p className="mt-1 text-sm text-gray-500">
          상품 x 판매자 가격을 한눈에 관리합니다. 셀을 클릭하여 가격을 수정하세요.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {/* Matrix Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
        <table className="w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider sticky left-0 bg-gray-50 z-10">
                상품
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                기본가
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                원가
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                할인율
              </th>
              {sellers.map((seller) => (
                <th key={seller.id} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                  {seller.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={sellers.length + 4} className="px-4 py-8 text-center text-gray-500 text-sm">
                  데이터가 없습니다.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.product_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 sticky left-0 bg-white z-10 whitespace-nowrap">
                    {row.product_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-600 font-mono">
                    {formatCurrency(row.base_price)}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-500 font-mono">
                    {(row as any).cost_price ? formatCurrency((row as any).cost_price) : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-500">
                    {(row as any).reduction_rate ? `${(row as any).reduction_rate}%` : '-'}
                  </td>
                  {sellers.map((seller) => {
                    const price = row.prices[seller.id] || 0;
                    const isEditing =
                      editingCell?.productId === row.product_id &&
                      editingCell?.sellerId === seller.id;
                    const isDifferent = price > 0 && price !== row.base_price;

                    return (
                      <td
                        key={seller.id}
                        className={`px-4 py-3 text-sm text-right ${isDifferent ? 'bg-yellow-50' : ''}`}
                      >
                        {isEditing ? (
                          <div className="flex items-center justify-end gap-1">
                            <input
                              type="number"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              onKeyDown={handleKeyDown}
                              autoFocus
                              className="w-24 px-2 py-1 text-right text-sm border border-primary-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                            />
                            <Button size="sm" onClick={handleSave} loading={saving}>
                              저장
                            </Button>
                          </div>
                        ) : (
                          <button
                            onClick={() => handleCellClick(row.product_id, seller.id, price)}
                            className={`font-mono hover:bg-primary-50 px-2 py-1 rounded transition-colors ${
                              price > 0 ? 'text-gray-900' : 'text-gray-300'
                            }`}
                          >
                            {price > 0 ? formatCurrency(price) : '-'}
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400">
        노란색 셀은 기본가와 다른 가격이 설정된 항목입니다.
      </p>
    </div>
  );
}
