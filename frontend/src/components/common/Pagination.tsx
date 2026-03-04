import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  totalItems?: number;
  pageSize?: number;
}

export default function Pagination({
  page,
  totalPages,
  onPageChange,
  totalItems,
  pageSize,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: (number | string)[] = [];
  const maxVisible = 5;

  if (totalPages <= maxVisible + 2) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    const start = Math.max(2, page - 1);
    const end = Math.min(totalPages - 1, page + 1);

    if (start > 2) pages.push('...');
    for (let i = start; i <= end; i++) pages.push(i);
    if (end < totalPages - 1) pages.push('...');
    pages.push(totalPages);
  }

  const startItem = totalItems ? (page - 1) * (pageSize || 20) + 1 : 0;
  const endItem = totalItems
    ? Math.min(page * (pageSize || 20), totalItems)
    : 0;

  return (
    <div className="flex items-center justify-between px-2 py-3">
      {totalItems !== undefined && (
        <p className="text-sm text-gray-400">
          총 <span className="font-medium">{totalItems}</span>건 중{' '}
          <span className="font-medium">{startItem}</span>-
          <span className="font-medium">{endItem}</span>
        </p>
      )}

      <nav className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 1}
          className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-surface-raised disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeftIcon className="h-4 w-4" />
        </button>

        {pages.map((p, idx) =>
          typeof p === 'string' ? (
            <span key={`ellipsis-${idx}`} className="px-2 text-gray-500">
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`
                min-w-[36px] h-9 rounded-lg text-sm font-medium transition-colors
                ${
                  p === page
                    ? 'bg-primary-600 text-white'
                    : 'text-gray-400 hover:bg-surface-raised'
                }
              `}
            >
              {p}
            </button>
          ),
        )}

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page === totalPages}
          className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-surface-raised disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRightIcon className="h-4 w-4" />
        </button>
      </nav>
    </div>
  );
}
