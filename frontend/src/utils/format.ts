/**
 * Format a number as Korean Won currency
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format a number with comma separators
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('ko-KR').format(num);
}

/**
 * Format ISO date string to Korean date format
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

/**
 * Format ISO date string to Korean datetime format
 */
export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

/**
 * Format relative time (e.g., "3분 전", "1시간 전")
 */
export function formatRelativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const diff = now.getTime() - date.getTime();

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  const months = Math.floor(days / 30);

  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  if (hours < 24) return `${hours}시간 전`;
  if (days < 30) return `${days}일 전`;
  if (months < 12) return `${months}개월 전`;
  return formatDate(dateString);
}

/**
 * Get Korean label for order status
 */
export function getOrderStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: '임시저장',
    submitted: '접수완료',
    payment_confirmed: '입금확인',
    processing: '처리중',
    completed: '완료',
    cancelled: '취소',
    rejected: '반려',
  };
  return labels[status] || status;
}

/**
 * Get Korean label for campaign status
 */
export function getCampaignStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '대기',
    queued: '대기열',
    registering: '등록중',
    active: '활성',
    paused: '일시정지',
    completed: '완료',
    failed: '실패',
    expired: '만료',
  };
  return labels[status] || status;
}

/**
 * Get Korean label for user role
 */
export function getRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    system_admin: '시스템 관리자',
    company_admin: '회사 관리자',
    order_handler: '접수 담당자',
    distributor: '총판',
    sub_account: '하부계정',
  };
  return labels[role] || role;
}

/**
 * Get color class for order status badge
 */
export function getOrderStatusColor(status: string): string {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-800',
    submitted: 'bg-blue-100 text-blue-800',
    payment_confirmed: 'bg-green-100 text-green-800',
    processing: 'bg-yellow-100 text-yellow-800',
    completed: 'bg-emerald-100 text-emerald-800',
    cancelled: 'bg-red-100 text-red-800',
    rejected: 'bg-orange-100 text-orange-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

/**
 * Get color class for campaign status badge
 */
export function getCampaignStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-800',
    queued: 'bg-blue-100 text-blue-800',
    registering: 'bg-blue-100 text-blue-800',
    active: 'bg-green-100 text-green-800',
    paused: 'bg-yellow-100 text-yellow-800',
    completed: 'bg-emerald-100 text-emerald-800',
    failed: 'bg-red-100 text-red-800',
    expired: 'bg-orange-100 text-orange-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

/**
 * Get Korean label for campaign type
 */
export function getCampaignTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    traffic: '트래픽',
    save: '저장하기',
    directions: '길찾기',
  };
  return labels[type] || type;
}

/**
 * Get pipeline stage Korean label
 */
export function getPipelineStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    order_received: '주문접수',
    payment_confirmed: '입금확인',
    extraction_queued: '추출대기',
    extracting: '추출중',
    extraction_done: '추출완료',
    auto_assign: '자동배정',
    assignment_confirmed: '배정확인',
    registration_queued: '등록대기',
    registering: '등록중',
    active: '활성',
    completed: '완료',
    failed: '실패',
  };
  return labels[stage] || stage;
}

/**
 * Get Korean label for settlement status
 */
export function getSettlementStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '대기',
    confirmed: '확인',
    settled: '정산완료',
  };
  return labels[status] || status;
}

/**
 * Get color class for settlement status badge
 */
export function getSettlementStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    confirmed: 'bg-blue-100 text-blue-800',
    settled: 'bg-green-100 text-green-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

/**
 * Get Korean label for notification type
 */
export function getNotificationTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    order: '주문',
    campaign: '캠페인',
    system: '시스템',
    settlement: '정산',
  };
  return labels[type] || type;
}

/**
 * Get icon color class for notification type
 */
export function getNotificationTypeColor(type: string): string {
  const colors: Record<string, string> = {
    order: 'text-blue-500',
    campaign: 'text-green-500',
    system: 'text-gray-500',
    settlement: 'text-purple-500',
  };
  return colors[type] || 'text-gray-500';
}

/**
 * Get extended campaign status labels (includes quantum campaign statuses)
 */
export function getCampaignExtendedStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '대기중',
    queued: '대기열',
    registering: '등록중',
    active: '진행중',
    daily_exhausted: '일일소진',
    campaign_exhausted: '전체소진',
    paused: '일시정지',
    deactivated: '중단',
    pending_extend: '연장대기',
    completed: '종료',
    failed: '실패',
    expired: '만료',
  };
  return labels[status] || status;
}

/**
 * Get extended campaign status color
 */
export function getCampaignExtendedStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-800',
    queued: 'bg-blue-100 text-blue-800',
    registering: 'bg-yellow-100 text-yellow-800',
    active: 'bg-green-100 text-green-800',
    daily_exhausted: 'bg-orange-100 text-orange-800',
    campaign_exhausted: 'bg-red-100 text-red-800',
    paused: 'bg-yellow-100 text-yellow-800',
    deactivated: 'bg-red-100 text-red-800',
    pending_extend: 'bg-purple-100 text-purple-800',
    completed: 'bg-gray-100 text-gray-800',
    failed: 'bg-red-100 text-red-800',
    expired: 'bg-orange-100 text-orange-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

/**
 * Get keyword status label
 */
export function getKeywordStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    normal: '충분',
    warning: '부족',
    critical: '긴급',
  };
  return labels[status] || status;
}

/**
 * Get keyword status color
 */
export function getKeywordStatusColor(status: string): string {
  const colors: Record<string, string> = {
    normal: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    critical: 'bg-red-100 text-red-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

/**
 * Download a blob as a file
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
