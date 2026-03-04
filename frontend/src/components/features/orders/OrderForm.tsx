import { useState, type FormEvent } from 'react';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import type { Product, CreateOrderRequest } from '@/types';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';

interface OrderFormProps {
  products: Product[];
  onSubmit: (data: CreateOrderRequest) => void;
  loading?: boolean;
}

interface OrderItemInput {
  product_id: number;
  place_url: string;
  quantity: number;
}

export default function OrderForm({ products, onSubmit, loading }: OrderFormProps) {
  const [items, setItems] = useState<OrderItemInput[]>([
    { product_id: products[0]?.id || 0, place_url: '', quantity: 1 },
  ]);
  const [notes, setNotes] = useState('');

  const addItem = () => {
    setItems([
      ...items,
      { product_id: products[0]?.id || 0, place_url: '', quantity: 1 },
    ]);
  };

  const removeItem = (index: number) => {
    if (items.length <= 1) return;
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index: number, field: keyof OrderItemInput, value: string | number) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: value };
    setItems(newItems);
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      items: items.map((item) => ({
        product_id: item.product_id,
        quantity: item.quantity,
        item_data: { place_url: item.place_url },
      })),
      notes: notes || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Items */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-100">주문 항목</h3>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={addItem}
            icon={<PlusIcon className="h-4 w-4" />}
          >
            항목 추가
          </Button>
        </div>

        {items.map((item, index) => (
          <div
            key={index}
            className="p-4 border border-border rounded-lg space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-300">
                항목 {index + 1}
              </span>
              {items.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeItem(index)}
                  className="p-1 text-gray-400 hover:text-danger-500 transition-colors"
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  상품 <span className="text-danger-500">*</span>
                </label>
                <select
                  value={item.product_id}
                  onChange={(e) =>
                    updateItem(index, 'product_id', Number(e.target.value))
                  }
                  className="block w-full rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
                  required
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <Input
                label="네이버 플레이스 URL"
                type="url"
                placeholder="https://map.naver.com/..."
                value={item.place_url}
                onChange={(e) =>
                  updateItem(index, 'place_url', e.target.value)
                }
                required
              />

              <Input
                label="수량"
                type="number"
                min={1}
                value={item.quantity}
                onChange={(e) =>
                  updateItem(index, 'quantity', Number(e.target.value))
                }
                required
              />
            </div>
          </div>
        ))}
      </div>

      {/* Notes */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          메모 (선택)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="block w-full rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400 placeholder:text-gray-400"
          placeholder="주문에 대한 메모를 입력하세요..."
        />
      </div>

      <div className="flex justify-end">
        <Button type="submit" loading={loading} size="lg">
          주문 생성
        </Button>
      </div>
    </form>
  );
}
