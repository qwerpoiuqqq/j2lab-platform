import { useMemo } from 'react';
import type { Product } from '@/types';

interface CategorySelectorProps {
  products: Product[];
  onSelect: (category: string) => void;
}

export default function CategorySelector({ products, onSelect }: CategorySelectorProps) {
  const categories = useMemo(() => {
    const map = new Map<string, { count: number; minPrice: number }>();
    for (const p of products) {
      const cat = p.category || '기타';
      const existing = map.get(cat);
      if (existing) {
        existing.count += 1;
        existing.minPrice = Math.min(existing.minPrice, p.base_price);
      } else {
        map.set(cat, { count: 1, minPrice: p.base_price });
      }
    }
    return Array.from(map.entries()).map(([name, info]) => ({
      name,
      count: info.count,
      minPrice: info.minPrice,
    }));
  }, [products]);

  if (categories.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        등록된 상품이 없습니다.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {categories.map((cat) => (
        <button
          key={cat.name}
          onClick={() => onSelect(cat.name)}
          className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 text-left hover:border-primary-400 hover:shadow-md transition-all group"
        >
          <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary-600">
            {cat.name}
          </h3>
          <p className="mt-2 text-sm text-gray-500">
            {cat.count}개 상품
          </p>
        </button>
      ))}
    </div>
  );
}
