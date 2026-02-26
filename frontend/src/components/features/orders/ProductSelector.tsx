import type { Product } from '@/types';
import { formatCurrency } from '@/utils/format';

interface ProductSelectorProps {
  products: Product[];
  category: string;
  onSelect: (product: Product) => void;
}

export default function ProductSelector({ products, category, onSelect }: ProductSelectorProps) {
  const filtered = products.filter((p) => (p.category || '기타') === category);

  if (filtered.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        이 카테고리에 상품이 없습니다.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {filtered.map((product) => (
        <button
          key={product.id}
          onClick={() => onSelect(product)}
          className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 text-left hover:border-primary-400 hover:shadow-md transition-all group"
        >
          <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary-600">
            {product.name}
          </h3>
          <p className="mt-1 text-sm font-medium text-primary-600">
            {formatCurrency(product.base_price)}
          </p>
          {product.description && (
            <p className="mt-2 text-sm text-gray-500 line-clamp-2">
              {product.description}
            </p>
          )}
          {(product.min_work_days || product.max_work_days) && (
            <p className="mt-2 text-xs text-gray-400">
              작업기간: {product.min_work_days ?? '-'} ~ {product.max_work_days ?? '-'}일
            </p>
          )}
        </button>
      ))}
    </div>
  );
}
