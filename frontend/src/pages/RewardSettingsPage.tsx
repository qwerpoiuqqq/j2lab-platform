import { useState, useEffect, useMemo, useCallback } from 'react';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import { networkPresetsApi } from '@/api/networkPresets';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import { companiesApi } from '@/api/companies';
import type {
  NetworkPreset,
  SuperapAccount,
  Company,
  CampaignType,
} from '@/types';

// ---------------------------------------------------------------------------
const TYPE_LABELS: Record<string, string> = {
  traffic: '트래픽',
  save: '저장하기',
  directions: '길찾기',
};
const CAMPAIGN_TYPES: CampaignType[] = ['traffic', 'save', 'directions'];

// ---------------------------------------------------------------------------
interface NetworkForm {
  name: string;
  campaign_type: CampaignType;
  extension_threshold: number;
  selectedAccountId: number | null;
}

const EMPTY_FORM: NetworkForm = {
  name: '',
  campaign_type: 'traffic',
  extension_threshold: 10000,
  selectedAccountId: null,
};

// ===========================================================================
export default function RewardSettingsPage() {
  // ---- data ----
  const [companies, setCompanies] = useState<Company[]>([]);
  const [presets, setPresets] = useState<NetworkPreset[]>([]);
  const [accounts, setAccounts] = useState<SuperapAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---- modal ----
  const [modalOpen, setModalOpen] = useState(false);
  const [editPreset, setEditPreset] = useState<NetworkPreset | null>(null);
  const [modalCompanyId, setModalCompanyId] = useState(0);
  const [modalCompanyName, setModalCompanyName] = useState('');
  const [form, setForm] = useState<NetworkForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // ---- delete ----
  const [deleteTarget, setDeleteTarget] = useState<NetworkPreset | null>(null);
  const [deleting, setDeleting] = useState(false);

  // ---- drag ----
  const [dragInfo, setDragInfo] = useState<{
    companyId: number;
    type: string;
    idx: number;
  } | null>(null);

  // ---- fetch ----
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [compRes, presetRes, acctRes] = await Promise.all([
        companiesApi.list(1, 100),
        networkPresetsApi.list({ size: 100 }),
        campaignAccountsApi.list({ size: 100 }),
      ]);
      setCompanies(compRes.items);
      setPresets(presetRes.items);
      setAccounts(acctRes.items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '데이터를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ---- derived ----

  // 프리셋별 연결된 계정 목록 (1개 이상일 수 있음 — 레거시)
  const acctsByPreset = useMemo(() => {
    const m: Record<number, SuperapAccount[]> = {};
    for (const a of accounts) {
      if (a.network_preset_id) {
        if (!m[a.network_preset_id]) m[a.network_preset_id] = [];
        m[a.network_preset_id].push(a);
      }
    }
    return m;
  }, [accounts]);

  // 프리셋 이름 매핑 (드롭다운 라벨용)
  const presetNames = useMemo(() => {
    const m: Record<number, string> = {};
    for (const p of presets) m[p.id] = p.name;
    return m;
  }, [presets]);

  // 프리셋 그룹: company → campaign_type → presets (tier_order 정렬)
  const grouped = useMemo(() => {
    const result: Record<number, Record<string, NetworkPreset[]>> = {};
    for (const p of presets) {
      if (!result[p.company_id]) result[p.company_id] = {};
      if (!result[p.company_id][p.campaign_type])
        result[p.company_id][p.campaign_type] = [];
      result[p.company_id][p.campaign_type].push(p);
    }
    for (const cid of Object.keys(result)) {
      for (const ct of Object.keys(result[Number(cid)])) {
        result[Number(cid)][ct].sort((a, b) => a.tier_order - b.tier_order);
      }
    }
    return result;
  }, [presets]);

  const companyMap = useMemo(() => {
    const m: Record<number, string> = {};
    for (const c of companies) m[c.id] = c.name;
    return m;
  }, [companies]);

  const unassigned = useMemo(
    () => accounts.filter((a) => !a.network_preset_id),
    [accounts],
  );

  // ---- helpers ----
  const setField = <K extends keyof NetworkForm>(
    key: K,
    value: NetworkForm[K],
  ) => setForm((prev) => ({ ...prev, [key]: value }));

  // ---- open modals ----
  const openAdd = (companyId: number) => {
    setEditPreset(null);
    setModalCompanyId(companyId);
    setModalCompanyName(companyMap[companyId] || '');
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (preset: NetworkPreset) => {
    const linked = acctsByPreset[preset.id] || [];
    setEditPreset(preset);
    setModalCompanyId(preset.company_id);
    setModalCompanyName(companyMap[preset.company_id] || '');
    setForm({
      name: preset.name,
      campaign_type: preset.campaign_type as CampaignType,
      extension_threshold: preset.extension_threshold ?? 10000,
      selectedAccountId: linked.length > 0 ? linked[0].id : null,
    });
    setModalOpen(true);
  };

  // ---- save ----
  const handleSave = async () => {
    if (!form.name.trim()) {
      alert('네트워크 이름을 입력하세요.');
      return;
    }

    setSaving(true);
    try {
      if (editPreset) {
        // === UPDATE ===
        await networkPresetsApi.update(editPreset.id, {
          name: form.name,
          extension_threshold: form.extension_threshold,
        });

        const prevLinked = acctsByPreset[editPreset.id] || [];
        const newAcctId = form.selectedAccountId;

        // 기존에 연결된 모든 계정 해제 (선택된 계정 제외)
        for (const pa of prevLinked) {
          if (pa.id !== newAcctId) {
            await campaignAccountsApi.update(pa.id, {
              network_preset_id: null,
            });
          }
        }

        // 새 계정 연결 (이미 연결된 경우가 아닐 때만)
        if (newAcctId && !prevLinked.some((a) => a.id === newAcctId)) {
          // 새 계정이 다른 프리셋에 연결되어 있으면 그쪽에서 해제됨 (서버측 처리)
          await campaignAccountsApi.update(newAcctId, {
            network_preset_id: editPreset.id,
          });
        }
      } else {
        // === CREATE ===
        const existing =
          grouped[modalCompanyId]?.[form.campaign_type] || [];
        const nextTier =
          existing.length > 0
            ? Math.max(...existing.map((p) => p.tier_order)) + 1
            : 1;

        const newPreset = await networkPresetsApi.create({
          company_id: modalCompanyId,
          campaign_type: form.campaign_type,
          tier_order: nextTier,
          name: form.name,
          extension_threshold: form.extension_threshold,
        });

        // 선택된 계정을 새 프리셋에 연결
        if (form.selectedAccountId) {
          await campaignAccountsApi.update(form.selectedAccountId, {
            network_preset_id: newPreset.id,
          });
        }
      }

      setModalOpen(false);
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  // ---- delete ----
  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      // 연결된 모든 계정 해제 (삭제X, 미연결로)
      const linked = acctsByPreset[deleteTarget.id] || [];
      for (const a of linked) {
        await campaignAccountsApi.update(a.id, { network_preset_id: null });
      }
      await networkPresetsApi.delete(deleteTarget.id);
      setDeleteTarget(null);
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제에 실패했습니다.');
    } finally {
      setDeleting(false);
    }
  };

  // ---- drag reorder ----
  const onDragStart = (
    e: React.DragEvent,
    companyId: number,
    type: string,
    idx: number,
  ) => {
    e.dataTransfer.effectAllowed = 'move';
    setDragInfo({ companyId, type, idx });
  };

  const onDrop = async (
    e: React.DragEvent,
    companyId: number,
    type: string,
    dropIdx: number,
  ) => {
    e.preventDefault();
    if (
      !dragInfo ||
      dragInfo.companyId !== companyId ||
      dragInfo.type !== type
    ) {
      setDragInfo(null);
      return;
    }
    const dragIdx = dragInfo.idx;
    setDragInfo(null);
    if (dragIdx === dropIdx) return;

    const list = grouped[companyId]?.[type];
    if (!list) return;

    const reordered = [...list];
    const [moved] = reordered.splice(dragIdx, 1);
    reordered.splice(dropIdx, 0, moved);

    try {
      await Promise.all(
        reordered.map((p, i) =>
          p.tier_order !== i + 1
            ? networkPresetsApi.update(p.id, { tier_order: i + 1 })
            : Promise.resolve(null),
        ),
      );
      await fetchData();
    } catch {
      alert('순서 변경에 실패했습니다.');
      await fetchData();
    }
  };

  // =========================================================================
  // RENDER
  // =========================================================================

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            네트워크 배정 설정
          </h1>
          <p className="mt-1 text-sm text-gray-400">로딩 중...</p>
        </div>
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="animate-pulse bg-surface-raised rounded-xl h-48"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">
          네트워크 배정 설정
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          드래그하여 배정 순서를 변경하세요. 위에서부터 우선 배정됩니다.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* ---- Per-company sections ---- */}
      {companies.map((company) => {
        const compPresets = grouped[company.id] || {};
        const hasAny = Object.values(compPresets).some((l) => l.length > 0);

        return (
          <div
            key={company.id}
            className="bg-surface rounded-xl border border-border shadow-sm"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
              <h2 className="text-lg font-bold text-gray-100">
                {company.name}
              </h2>
              <button
                onClick={() => openAdd(company.id)}
                className="text-sm text-primary-400 hover:text-primary-300 font-medium"
              >
                + 네트워크 추가
              </button>
            </div>

            <div className="p-6 space-y-6">
              {!hasAny && (
                <div className="text-center py-8 text-gray-400 text-sm">
                  등록된 네트워크가 없습니다.
                </div>
              )}

              {CAMPAIGN_TYPES.map((ct) => {
                const list = compPresets[ct];
                if (!list || list.length === 0) return null;

                return (
                  <div key={ct}>
                    <div className="mb-3">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${
                          ct === 'traffic'
                            ? 'bg-blue-900/30 text-primary-300'
                            : ct === 'save'
                              ? 'bg-green-900/30 text-green-400'
                              : 'bg-purple-900/30 text-purple-400'
                        }`}
                      >
                        {TYPE_LABELS[ct]} ({list.length})
                      </span>
                    </div>

                    <div className="space-y-2">
                      {list.map((preset, idx) => {
                        const linked = acctsByPreset[preset.id] || [];
                        const isDragOver =
                          dragInfo?.companyId === company.id &&
                          dragInfo?.type === ct &&
                          dragInfo?.idx !== idx;

                        return (
                          <div
                            key={preset.id}
                            draggable
                            onDragStart={(e) =>
                              onDragStart(e, company.id, ct, idx)
                            }
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={(e) => onDrop(e, company.id, ct, idx)}
                            className={`flex items-center gap-3 px-4 py-3 rounded-lg bg-surface-raised hover:bg-surface-raised transition-colors group cursor-grab active:cursor-grabbing ${
                              isDragOver
                                ? 'border-2 border-dashed border-primary-400'
                                : 'border border-transparent'
                            }`}
                          >
                            <span className="text-gray-300 select-none text-sm">
                              ⠿
                            </span>

                            <span className="w-7 h-7 rounded-full bg-primary-900/30 text-primary-300 flex items-center justify-center text-sm font-bold flex-shrink-0">
                              {idx + 1}
                            </span>

                            <div className="flex-1 min-w-0">
                              <div className="font-medium text-gray-100 text-sm">
                                {preset.name}
                              </div>
                              <div className="text-xs text-gray-400 mt-0.5">
                                연장 기준 {preset.extension_threshold ?? 10000}타
                              </div>
                              {linked.length > 0 ? (
                                <div className="text-xs text-gray-400 mt-0.5">
                                  {linked.map((a, i) => (
                                    <span key={a.id}>
                                      {i > 0 && ' / '}
                                      {a.user_id_superap}
                                      {a.agency_name &&
                                        ` (${a.agency_name})`}
                                      {` · ${a.unit_cost_traffic}/${a.unit_cost_save}원`}
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <div className="text-xs text-orange-500 mt-0.5">
                                  계정 미연결
                                </div>
                              )}
                            </div>

                            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={() => openEdit(preset)}
                                className="text-xs text-primary-400 hover:text-primary-300 font-medium"
                              >
                                편집
                              </button>
                              <button
                                onClick={() => setDeleteTarget(preset)}
                                className="text-xs text-red-500 hover:text-red-400 font-medium"
                              >
                                삭제
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* ---- Unassigned accounts ---- */}
      {unassigned.length > 0 && (
        <div className="bg-surface rounded-xl border border-orange-800 shadow-sm">
          <div className="px-6 py-4 border-b border-orange-800">
            <h2 className="text-base font-bold text-orange-400">
              미연결 계정 ({unassigned.length}개)
            </h2>
          </div>
          <div className="p-4 space-y-1">
            {unassigned.map((acct) => (
              <div
                key={acct.id}
                className="flex items-center gap-3 px-4 py-2 rounded-lg bg-orange-900/20"
              >
                <span className="text-orange-400">•</span>
                <span className="flex-1 text-sm text-gray-300">
                  {acct.user_id_superap}
                  {acct.agency_name && ` · ${acct.agency_name}`}
                  {acct.company_id
                    ? ` · ${companyMap[acct.company_id] || ''}`
                    : ''}
                  {` · ${acct.unit_cost_traffic}/${acct.unit_cost_save}원`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* Create / Edit Modal                                               */}
      {/* ================================================================= */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={
          editPreset
            ? '네트워크 편집'
            : `${modalCompanyName} — 네트워크 추가`
        }
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>
              취소
            </Button>
            <Button onClick={handleSave} loading={saving}>
              저장
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {/* Context (edit mode) */}
          {editPreset && (
            <div className="text-sm text-gray-400 bg-surface-raised rounded-lg px-3 py-2">
              {modalCompanyName} · {TYPE_LABELS[form.campaign_type]} ·{' '}
              {editPreset.tier_order}순위
            </div>
          )}

          {/* Campaign type (create only) */}
          {!editPreset && (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                캠페인 타입
              </label>
              <div className="flex gap-2">
                {CAMPAIGN_TYPES.map((ct) => (
                  <button
                    key={ct}
                    type="button"
                    onClick={() => setField('campaign_type', ct)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                      form.campaign_type === ct
                        ? 'bg-primary-600 text-white'
                        : 'bg-surface-raised text-gray-400 hover:bg-surface-raised'
                    }`}
                  >
                    {TYPE_LABELS[ct]}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Network name */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              네트워크 이름
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setField('name', e.target.value)}
              placeholder="예: 제이투랩 저장 1순위"
              className="w-full px-3 py-2 border border-border-strong rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              연장/신규 기준 타수
            </label>
            <input
              type="number"
              min={0}
              value={form.extension_threshold}
              onChange={(e) => setField('extension_threshold', Number(e.target.value || 0))}
              className="w-full px-3 py-2 border border-border-strong rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
            />
            <p className="mt-1 text-xs text-gray-400">
              (기존 + 신규) 총 한도가 이 값 미만이면 연장, 이상이면 신규로 배정됩니다.
            </p>
          </div>

          {/* ---- Account selection (ALL accounts) ---- */}
          <div className="border-t border-border pt-4">
            <label className="block text-sm font-semibold text-gray-300 mb-2">
              슈퍼앱 계정 연결
            </label>
            <select
              value={form.selectedAccountId ?? ''}
              onChange={(e) =>
                setField(
                  'selectedAccountId',
                  e.target.value ? Number(e.target.value) : null,
                )
              }
              className="w-full px-3 py-2 border border-border-strong rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface bg-surface text-gray-200"
            >
              <option value="">-- 계정 선택 --</option>

              {/* 미연결 계정 */}
              {unassigned.length > 0 && (
                <optgroup label="미연결 계정">
                  {unassigned.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.user_id_superap}
                      {a.agency_name ? ` (${a.agency_name})` : ''}
                      {` — ${a.unit_cost_traffic}/${a.unit_cost_save}원`}
                    </option>
                  ))}
                </optgroup>
              )}

              {/* 이미 연결된 계정 */}
              {accounts.filter((a) => a.network_preset_id).length > 0 && (
                <optgroup label="연결됨 (선택 시 이동)">
                  {accounts
                    .filter((a) => a.network_preset_id)
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.user_id_superap}
                        {a.agency_name ? ` (${a.agency_name})` : ''}
                        {` — ${a.unit_cost_traffic}/${a.unit_cost_save}원`}
                        {a.network_preset_id
                          ? ` [${presetNames[a.network_preset_id] || '?'}]`
                          : ''}
                      </option>
                    ))}
                </optgroup>
              )}
            </select>
            <p className="mt-1 text-xs text-gray-400">
              이미 다른 네트워크에 연결된 계정을 선택하면 이 네트워크로
              이동됩니다.
            </p>
          </div>

          {/* Selected account info */}
          {form.selectedAccountId && (() => {
            const sel = accounts.find((a) => a.id === form.selectedAccountId);
            if (!sel) return null;
            return (
              <div className="bg-surface-raised rounded-lg p-3 space-y-1">
                <div className="text-xs text-gray-400">
                  <span className="font-medium text-gray-300">아이디:</span>{' '}
                  {sel.user_id_superap}
                </div>
                {sel.agency_name && (
                  <div className="text-xs text-gray-400">
                    <span className="font-medium text-gray-300">
                      대행사:
                    </span>{' '}
                    {sel.agency_name}
                  </div>
                )}
                <div className="text-xs text-gray-400">
                  <span className="font-medium text-gray-300">원가:</span>{' '}
                  트래픽 {sel.unit_cost_traffic}원 / 저장 {sel.unit_cost_save}
                  원
                </div>
                {sel.network_preset_id &&
                  sel.network_preset_id !== editPreset?.id && (
                    <div className="text-xs text-orange-400 font-medium mt-1">
                      현재 &quot;{presetNames[sel.network_preset_id]}&quot;에
                      연결됨 — 저장 시 이 네트워크로 이동됩니다
                    </div>
                  )}
              </div>
            );
          })()}
        </div>
      </Modal>

      {/* ================================================================= */}
      {/* Delete Confirm Modal                                              */}
      {/* ================================================================= */}
      <Modal
        isOpen={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="네트워크 삭제"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              취소
            </Button>
            <Button variant="danger" onClick={handleDelete} loading={deleting}>
              삭제
            </Button>
          </>
        }
      >
        <p className="text-sm text-gray-300">
          <strong>{deleteTarget?.name}</strong> 네트워크를 삭제하시겠습니까?
          <br />
          <span className="text-gray-400">
            연결된 계정은 삭제되지 않고 미연결 상태로 전환됩니다.
          </span>
        </p>
      </Modal>
    </div>
  );
}
