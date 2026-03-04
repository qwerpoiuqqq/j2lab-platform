import { useMemo } from 'react';
import type { Product } from '@/types';

interface CategorySelectorProps {
  products: Product[];
  onSelect: (category: string) => void;
}

const categoryIcons: Record<string, string> = {
  '트래픽': '\u{1F4CA}',
  '저장': '\u{1F516}',
  '자동완성': '\u{2728}',
  '영수증': '\u{1F9FE}',
};

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
      <div className="text-center py-12 text-gray-400">
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
          className="bg-surface rounded-xl border border-border shadow-sm p-6 text-left hover:border-primary-400 hover:shadow-md transition-all group"
        >
          <div className="flex items-center gap-2">
            <span className="text-2xl">{categoryIcons[cat.name] || '\u{1F4E6}'}</span>
            <h3 className="text-lg font-semibold text-gray-100 group-hover:text-primary-600">
              {cat.name}
            </h3>
          </div>
          <p className="mt-2 text-sm text-gray-400">
            {cat.count}개 상품
          </p>
        </button>
      ))}
    </div>
  );
}
