import type { CalcFormula, DateCalcFormula } from '@/types';

// Pipeline required/optional field constants
export const PIPELINE_REQUIRED_FIELDS = ['place_url'] as const;
export const PIPELINE_OPTIONAL_FIELDS = [
  'campaign_type', 'daily_limit', 'total_limit', 'duration_days',
  'target_count', 'max_rank', 'min_rank', 'name_keyword_ratio',
] as const;

export interface PresetField {
  name: string;
  label: string;
  type: 'text' | 'url' | 'number' | 'date' | 'select' | 'calc' | 'date_calc' | 'readonly' | 'checkbox';
  required?: boolean;
  is_quantity?: boolean;
  default?: string | number;
  description?: string;
  formula?: CalcFormula | DateCalcFormula;
  color?: string;
  sample?: string;
  options?: string[];
  group?: string;
}

export interface ProductPreset {
  id: string;
  name: string;
  description: string;
  category: string;
  fields: PresetField[];
}

/**
 * Build combined schema for traffic+save integrated order grid.
 * Common fields (place_url, start_date, keyword) + traffic group + save group.
 */
export function buildCombinedSchema(): PresetField[] {
  return [
    // Common fields
    { name: 'place_url', label: '플레이스 URL', type: 'url', required: true, color: '#4472C4' },
    { name: 'start_date', label: '시작일', type: 'date', required: true, color: '#00B050' },
    { name: 'target_keyword', label: '키워드', type: 'text', required: false, color: '#7030A0' },
    // Traffic group
    { name: 'traffic_enabled', label: '트래픽', type: 'checkbox', default: 1, color: '#E67E22' },
    { name: 'traffic_daily_limit', label: '트래픽 타수', type: 'number', required: true, color: '#FFC000', group: 'traffic_enabled' },
    { name: 'traffic_duration_days', label: '트래픽 기간', type: 'number', required: true, color: '#FFC000', group: 'traffic_enabled' },
    { name: 'traffic_total_limit', label: '트래픽 총타수', type: 'calc', formula: { fieldA: 'traffic_daily_limit', operator: '*', fieldB: 'traffic_duration_days' } as CalcFormula, color: '#333D4B', group: 'traffic_enabled' },
    { name: 'traffic_end_date', label: '트래픽 종료일', type: 'date_calc', formula: { dateField: 'start_date', daysField: 'traffic_duration_days' } as DateCalcFormula, color: '#333D4B', group: 'traffic_enabled' },
    // Save group
    { name: 'save_enabled', label: '저장', type: 'checkbox', default: 1, color: '#2ECC71' },
    { name: 'save_daily_limit', label: '저장 타수', type: 'number', required: true, color: '#FFC000', group: 'save_enabled' },
    { name: 'save_duration_days', label: '저장 기간', type: 'number', required: true, color: '#FFC000', group: 'save_enabled' },
    { name: 'save_total_limit', label: '저장 총타수', type: 'calc', formula: { fieldA: 'save_daily_limit', operator: '*', fieldB: 'save_duration_days' } as CalcFormula, color: '#333D4B', group: 'save_enabled' },
    { name: 'save_end_date', label: '저장 종료일', type: 'date_calc', formula: { dateField: 'start_date', daysField: 'save_duration_days' } as DateCalcFormula, color: '#333D4B', group: 'save_enabled' },
  ];
}

export const PRODUCT_PRESETS: ProductPreset[] = [
  {
    id: 'quantum_traffic',
    name: '트래픽',
    description: '네이버 플레이스 트래픽 캠페인',
    category: '퀀텀',
    fields: [
      { name: 'place_url', label: '플레이스 URL', type: 'url', required: true, color: '#4472C4' },
      { name: 'start_date', label: '작업 시작일', type: 'date', required: true, color: '#00B050' },
      { name: 'daily_limit', label: '일 작업량(타수)', type: 'number', required: true, is_quantity: true, color: '#FFC000' },
      { name: 'duration_days', label: '작업 기간(일)', type: 'number', required: true, color: '#FFC000' },
      { name: 'target_keyword', label: '목표 노출 키워드', type: 'text', required: false, color: '#7030A0' },
      { name: 'campaign_type', label: '캠페인 유형', type: 'readonly', default: 'traffic', description: '트래픽', color: '#333D4B' },
      { name: 'total_limit', label: '총 타수', type: 'calc', formula: { fieldA: 'daily_limit', operator: '*', fieldB: 'duration_days' }, color: '#333D4B' },
      { name: 'end_date', label: '종료일', type: 'date_calc', formula: { dateField: 'start_date', daysField: 'duration_days' }, color: '#333D4B' },
    ],
  },
  {
    id: 'quantum_save',
    name: '저장하기',
    description: '네이버 플레이스 저장 캠페인',
    category: '퀀텀',
    fields: [
      { name: 'place_url', label: '플레이스 URL', type: 'url', required: true, color: '#4472C4' },
      { name: 'start_date', label: '작업 시작일', type: 'date', required: true, color: '#00B050' },
      { name: 'daily_limit', label: '일 작업량(타수)', type: 'number', required: true, is_quantity: true, color: '#FFC000' },
      { name: 'duration_days', label: '작업 기간(일)', type: 'number', required: true, color: '#FFC000' },
      { name: 'target_keyword', label: '목표 노출 키워드', type: 'text', required: false, color: '#7030A0' },
      { name: 'campaign_type', label: '캠페인 유형', type: 'readonly', default: 'save', description: '저장하기', color: '#333D4B' },
      { name: 'total_limit', label: '총 타수', type: 'calc', formula: { fieldA: 'daily_limit', operator: '*', fieldB: 'duration_days' }, color: '#333D4B' },
      { name: 'end_date', label: '종료일', type: 'date_calc', formula: { dateField: 'start_date', daysField: 'duration_days' }, color: '#333D4B' },
    ],
  },
];
