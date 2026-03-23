import { useState, useEffect, useCallback } from 'react';
import Button from '@/components/common/Button';
import Input from '@/components/common/Input';
import Badge from '@/components/common/Badge';
import {
  CircleStackIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  UserIcon,
} from '@heroicons/react/24/outline';
import { formatNumber, formatDateTime } from '@/utils/format';
import { pointsApi } from '@/api/points';
import type { ChargeRequest } from '@/api/points';
import { useAuthStore } from '@/store/auth';

export default function PointsPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'system_admin' || user?.role === 'company_admin';
  const isDistributor = user?.role === 'distributor';

  // Balance state
  const [effectiveBalance, setEffectiveBalance] = useState<number | null>(null);
  const [currentBalance, setCurrentBalance] = useState<number | null>(null);
  const [pendingTotal, setPendingTotal] = useState<number>(0);
  const [balanceOwnerName, setBalanceOwnerName] = useState<string>('');
  const [balanceLoading, setBalanceLoading] = useState(true);

  // Charge requests (for admin view)
  const [pendingRequests, setPendingRequests] = useState<ChargeRequest[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);

  // Grant points (admin)
  const [grantableUsers, setGrantableUsers] = useState<Array<{ id: string; name: string; role: string; login_id: string }>>([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [grantAmount, setGrantAmount] = useState('');
  const [grantDescription, setGrantDescription] = useState('');
  const [granting, setGranting] = useState(false);
  const [grantError, setGrantError] = useState<string | null>(null);
  const [grantSuccess, setGrantSuccess] = useState<string | null>(null);

  // Submit charge request (distributor)
  const [chargeAmount, setChargeAmount] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Approval/rejection state
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState<Record<number, string>>({});

  const fetchBalance = useCallback(async () => {
    if (!user) return;
    setBalanceLoading(true);
    try {
      if (isAdmin) {
        // admin: just show their own balance
        const data = await pointsApi.getMyBalance(user.id);
        setCurrentBalance(data.balance);
        setEffectiveBalance(data.balance);
      } else {
        const data = await pointsApi.getEffectiveMyBalance();
        setEffectiveBalance(data.balance);
        setCurrentBalance(data.balance);
        setBalanceOwnerName(data.effective_user_name);
      }
    } catch {
      // silently fail
    } finally {
      setBalanceLoading(false);
    }
  }, [user, isAdmin]);

  const fetchPendingRequests = useCallback(async () => {
    if (!isAdmin) return;
    setRequestsLoading(true);
    try {
      const data = await pointsApi.listChargeRequests({ status: 'pending', limit: 50 });
      setPendingRequests(data.items);
      // sum pending totals
      const total = data.items.reduce((sum, r) => sum + r.amount, 0);
      setPendingTotal(total);
    } catch {
      // silently fail
    } finally {
      setRequestsLoading(false);
    }
  }, [isAdmin]);

  const fetchGrantableUsers = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const users = await pointsApi.getGrantableUsers();
      setGrantableUsers(users);
      if (users.length > 0) setSelectedUserId(users[0].id);
    } catch {
      // silently fail
    }
  }, [isAdmin]);

  // Distributor: fetch their own charge requests
  const [myRequests, setMyRequests] = useState<ChargeRequest[]>([]);
  const [myRequestsLoading, setMyRequestsLoading] = useState(false);

  const fetchMyRequests = useCallback(async () => {
    if (!isDistributor) return;
    setMyRequestsLoading(true);
    try {
      const data = await pointsApi.listChargeRequests({ limit: 20 });
      setMyRequests(data.items);
    } catch {
      // silently fail
    } finally {
      setMyRequestsLoading(false);
    }
  }, [isDistributor]);

  useEffect(() => {
    fetchBalance();
    if (isAdmin) {
      fetchPendingRequests();
      fetchGrantableUsers();
    }
    if (isDistributor) {
      fetchMyRequests();
    }
  }, [fetchBalance, fetchPendingRequests, fetchGrantableUsers, fetchMyRequests, isAdmin, isDistributor]);

  const handleApprove = async (id: number) => {
    setProcessingId(id);
    try {
      await pointsApi.approveChargeRequest(id);
      await fetchPendingRequests();
      await fetchBalance();
    } catch {
      // silently fail
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (id: number) => {
    setProcessingId(id);
    try {
      await pointsApi.rejectChargeRequest(id, rejectReason[id] || undefined);
      await fetchPendingRequests();
    } catch {
      // silently fail
    } finally {
      setProcessingId(null);
    }
  };

  const handleGrant = async () => {
    if (!selectedUserId || !grantAmount) return;
    const amount = parseInt(grantAmount, 10);
    if (isNaN(amount) || amount === 0) {
      setGrantError('유효한 금액을 입력하세요.');
      return;
    }
    setGranting(true);
    setGrantError(null);
    setGrantSuccess(null);
    try {
      await pointsApi.grantPoints(selectedUserId, amount, grantDescription || undefined);
      setGrantSuccess(`${formatNumber(Math.abs(amount))}P ${amount > 0 ? '지급' : '차감'} 완료`);
      setGrantAmount('');
      setGrantDescription('');
    } catch (e: any) {
      setGrantError(e?.response?.data?.detail || '포인트 지급 실패');
    } finally {
      setGranting(false);
    }
  };

  const handleChargeRequest = async () => {
    const amount = parseInt(chargeAmount, 10);
    if (isNaN(amount) || amount <= 0) {
      setSubmitError('유효한 금액을 입력하세요.');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    try {
      await pointsApi.createChargeRequest(amount);
      setSubmitSuccess('충전 요청이 제출되었습니다. 관리자 승인을 기다려주세요.');
      setChargeAmount('');
      await fetchMyRequests();
    } catch (e: any) {
      setSubmitError(e?.response?.data?.detail || '충전 요청 실패');
    } finally {
      setSubmitting(false);
    }
  };

  const statusBadge = (status: string) => {
    if (status === 'pending') return <Badge variant="warning">대기중</Badge>;
    if (status === 'approved') return <Badge variant="success">승인</Badge>;
    if (status === 'rejected') return <Badge variant="danger">거절</Badge>;
    return <Badge>{status}</Badge>;
  };

  const roleLabels: Record<string, string> = {
    distributor: '총판',
    order_handler: '담당자',
    system_admin: '관리자',
    company_admin: '경리',
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <CircleStackIcon className="h-7 w-7 text-primary-400" />
        <h1 className="text-2xl font-bold text-gray-100">포인트 관리</h1>
      </div>

      {/* Balance Card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-surface rounded-xl border border-border p-5">
          <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">유효 잔액</p>
          {balanceLoading ? (
            <div className="h-8 bg-surface-raised rounded animate-pulse" />
          ) : (
            <p className="text-2xl font-bold text-primary-300">
              {effectiveBalance !== null ? formatNumber(effectiveBalance) : '-'}P
            </p>
          )}
          {balanceOwnerName && !isAdmin && (
            <p className="text-xs text-gray-500 mt-1">기준: {balanceOwnerName}</p>
          )}
        </div>

        <div className="bg-surface rounded-xl border border-border p-5">
          <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">현재 잔액</p>
          {balanceLoading ? (
            <div className="h-8 bg-surface-raised rounded animate-pulse" />
          ) : (
            <p className="text-2xl font-bold text-gray-100">
              {currentBalance !== null ? formatNumber(currentBalance) : '-'}P
            </p>
          )}
        </div>

        {isAdmin && (
          <div className="bg-surface rounded-xl border border-border p-5">
            <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">대기 충전 합계</p>
            <p className="text-2xl font-bold text-orange-400">
              {formatNumber(pendingTotal)}P
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {pendingRequests.length}건 승인 대기
            </p>
          </div>
        )}

        {isDistributor && (
          <div className="bg-surface rounded-xl border border-border p-5">
            <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">대기 요청</p>
            <p className="text-2xl font-bold text-orange-400">
              {myRequests.filter((r) => r.status === 'pending').length}건
            </p>
            <p className="text-xs text-gray-500 mt-1">승인 대기 중</p>
          </div>
        )}
      </div>

      {/* Admin: Pending Charge Requests */}
      {isAdmin && (
        <div className="bg-surface rounded-xl border border-border overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
            <div className="flex items-center gap-2">
              <ClockIcon className="h-5 w-5 text-orange-400" />
              <h2 className="text-base font-semibold text-gray-100">충전 요청 승인 대기</h2>
              {pendingRequests.length > 0 && (
                <span className="flex items-center justify-center min-w-[20px] h-5 px-1 text-[11px] font-bold text-white bg-orange-500 rounded-full">
                  {pendingRequests.length}
                </span>
              )}
            </div>
            <button
              onClick={fetchPendingRequests}
              className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
            >
              새로고침
            </button>
          </div>

          {requestsLoading ? (
            <div className="p-6 text-center text-sm text-gray-500">로딩 중...</div>
          ) : pendingRequests.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-500">
              대기 중인 충전 요청이 없습니다
            </div>
          ) : (
            <div className="divide-y divide-border-subtle">
              {pendingRequests.map((req) => (
                <div key={req.id} className="px-6 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 bg-primary-900/30 rounded-full flex items-center justify-center shrink-0">
                        <UserIcon className="h-4 w-4 text-primary-400" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-100">
                          {req.user_name || req.user_id}
                          {req.user_login_id && (
                            <span className="ml-2 text-xs text-gray-500">({req.user_login_id})</span>
                          )}
                        </p>
                        <p className="text-xs text-gray-500">{formatDateTime(req.created_at)}</p>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-lg font-bold text-primary-300">
                        {formatNumber(req.amount)}P
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <Input
                      placeholder="거절 사유 (선택)"
                      value={rejectReason[req.id] || ''}
                      onChange={(e) =>
                        setRejectReason((prev) => ({ ...prev, [req.id]: e.target.value }))
                      }
                      className="flex-1 min-w-[160px] text-xs"
                    />
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => handleApprove(req.id)}
                      disabled={processingId === req.id}
                    >
                      <CheckCircleIcon className="h-4 w-4 mr-1" />
                      승인
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => handleReject(req.id)}
                      disabled={processingId === req.id}
                    >
                      <XCircleIcon className="h-4 w-4 mr-1" />
                      거절
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Admin: Grant Points */}
      {isAdmin && (
        <div className="bg-surface rounded-xl border border-border overflow-hidden">
          <div className="px-6 py-4 border-b border-border-subtle">
            <h2 className="text-base font-semibold text-gray-100">포인트 직접 지급 / 차감</h2>
            <p className="text-xs text-gray-500 mt-0.5">음수 금액 입력 시 차감 처리됩니다</p>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">대상 유저</label>
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="w-full bg-surface-raised border border-border rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {grantableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.login_id}) — {roleLabels[u.role] || u.role}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">금액 (P)</label>
                <Input
                  type="number"
                  placeholder="예: 10000 또는 -5000"
                  value={grantAmount}
                  onChange={(e) => setGrantAmount(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">메모 (선택)</label>
                <Input
                  placeholder="지급/차감 사유"
                  value={grantDescription}
                  onChange={(e) => setGrantDescription(e.target.value)}
                />
              </div>
            </div>

            {grantError && (
              <p className="text-sm text-red-400">{grantError}</p>
            )}
            {grantSuccess && (
              <p className="text-sm text-green-400">{grantSuccess}</p>
            )}

            <Button
              variant="primary"
              onClick={handleGrant}
              disabled={granting || !selectedUserId || !grantAmount}
            >
              {granting ? '처리 중...' : '포인트 지급/차감'}
            </Button>
          </div>
        </div>
      )}

      {/* Distributor: Submit Charge Request */}
      {isDistributor && (
        <div className="bg-surface rounded-xl border border-border overflow-hidden">
          <div className="px-6 py-4 border-b border-border-subtle">
            <h2 className="text-base font-semibold text-gray-100">충전 요청</h2>
            <p className="text-xs text-gray-500 mt-0.5">관리자 승인 후 포인트가 충전됩니다</p>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">충전 금액 (P)</label>
              <Input
                type="number"
                placeholder="예: 100000"
                value={chargeAmount}
                onChange={(e) => setChargeAmount(e.target.value)}
              />
            </div>

            {submitError && (
              <p className="text-sm text-red-400">{submitError}</p>
            )}
            {submitSuccess && (
              <p className="text-sm text-green-400">{submitSuccess}</p>
            )}

            <Button
              variant="primary"
              onClick={handleChargeRequest}
              disabled={submitting || !chargeAmount}
            >
              {submitting ? '요청 중...' : '충전 요청 제출'}
            </Button>
          </div>
        </div>
      )}

      {/* Distributor: My Charge Request History */}
      {isDistributor && (
        <div className="bg-surface rounded-xl border border-border overflow-hidden">
          <div className="px-6 py-4 border-b border-border-subtle">
            <h2 className="text-base font-semibold text-gray-100">충전 요청 내역</h2>
          </div>
          {myRequestsLoading ? (
            <div className="p-6 text-center text-sm text-gray-500">로딩 중...</div>
          ) : myRequests.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-500">충전 요청 내역이 없습니다</div>
          ) : (
            <div className="divide-y divide-border-subtle">
              {myRequests.map((req) => (
                <div key={req.id} className="px-6 py-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-100">
                      {formatNumber(req.amount)}P
                    </p>
                    <p className="text-xs text-gray-500">{formatDateTime(req.created_at)}</p>
                    {req.rejected_reason && (
                      <p className="text-xs text-red-400 mt-0.5">거절 사유: {req.rejected_reason}</p>
                    )}
                  </div>
                  <div>{statusBadge(req.status)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Order handler: balance only view — cards above are sufficient */}
      {user?.role === 'order_handler' && (
        <div className="bg-surface rounded-xl border border-border p-6 text-center text-sm text-gray-400">
          포인트 잔액은 위 카드에서 확인하세요. 충전은 담당 총판을 통해 요청하세요.
        </div>
      )}
    </div>
  );
}
