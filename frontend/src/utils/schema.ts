import type { FormFieldExtended, CalcFormula, DateCalcFormula } from '@/types';

/**
 * Normalize schema from various formats to the standard array format.
 *
 * Old format: { fields: [{ key, type, label, required, options }] }
 * New format: [{ name, label, type, required, color, sample, formula, options, is_quantity, description }]
 */
export function normalizeSchema(raw: any): FormFieldExtended[] {
  if (!raw) return [];

  // Already an array → new format
  if (Array.isArray(raw)) {
    return raw.map(normalizeField);
  }

  // Old format: { fields: [...] }
  if (raw.fields && Array.isArray(raw.fields)) {
    return raw.fields.map((f: any) => normalizeField({
      ...f,
      name: f.name || f.key,  // old format uses 'key', new uses 'name'
    }));
  }

  return [];
}

function normalizeField(f: any): FormFieldExtended {
  // Migrate legacy formula formats to new object format
  let formula = f.formula;

  if (f.type === 'calc' && typeof formula === 'string' && formula) {
    // Legacy string formula "fieldA * fieldB" → { fieldA, operator, fieldB }
    const parsed = parseLegacyCalcFormula(formula);
    if (parsed) formula = parsed;
  } else if (f.type === 'date_calc' && !formula && f.base_field && f.days_field) {
    // Legacy separate base_field/days_field → { dateField, daysField }
    formula = { dateField: f.base_field, daysField: f.days_field } as DateCalcFormula;
  }

  return {
    name: f.name || f.key || '',
    label: f.label || f.name || '',
    type: f.type || 'text',
    required: f.required ?? false,
    default: f.default,
    color: f.color,
    sample: f.sample,
    options: f.options,
    formula,
    is_quantity: f.is_quantity,
    description: f.description,
  };
}

/** Parse legacy string formula "fieldA * fieldB" into CalcFormula object */
function parseLegacyCalcFormula(str: string): CalcFormula | null {
  const ops = ['*', '+', '-', '/'] as const;
  for (const op of ops) {
    const idx = str.indexOf(` ${op} `);
    if (idx !== -1) {
      return {
        fieldA: str.substring(0, idx).trim(),
        operator: op,
        fieldB: str.substring(idx + 3).trim(),
      };
    }
  }
  return null;
}

/**
 * Type-safe helpers to extract formula parts
 */
export function getCalcFormula(field: FormFieldExtended): CalcFormula | null {
  if (field.type !== 'calc' || !field.formula) return null;
  if (typeof field.formula === 'object' && 'fieldA' in field.formula) {
    return field.formula as CalcFormula;
  }
  // Legacy string fallback
  if (typeof field.formula === 'string') {
    return parseLegacyCalcFormula(field.formula);
  }
  return null;
}

export function getDateCalcFormula(field: FormFieldExtended): DateCalcFormula | null {
  if (field.type !== 'date_calc' || !field.formula) return null;
  if (typeof field.formula === 'object' && 'dateField' in field.formula) {
    return field.formula as DateCalcFormula;
  }
  return null;
}

/**
 * Auto-generate field name from label (Korean-friendly)
 * e.g. "플레이스 URL" → "플레이스_url", "일 작업량(타수)" → "일_작업량(타수)"
 */
export function labelToName(label: string): string {
  if (!label) return '';
  return label
    .replace(/\s+/g, '_')
    .replace(/[^a-zA-Z0-9가-힣_()]/g, '')
    .toLowerCase() || 'field';
}

/**
 * Get sample value for a field based on its type.
 */
export function getSampleValue(field: FormFieldExtended, rowIndex: number): string {
  if (field.sample) return field.sample;

  switch (field.type) {
    case 'text':
      return rowIndex === 0 ? '샘플 텍스트' : '입력값';
    case 'url':
      return 'https://example.com';
    case 'number':
      return rowIndex === 0 ? '100' : '200';
    case 'date':
      return '2026-01-01';
    case 'select':
      return field.options?.[0] || '선택...';
    case 'calc':
      return '= 자동계산';
    case 'date_calc':
      return '= 자동계산';
    case 'readonly':
      return field.description || '자동 입력';
    default:
      return '';
  }
}
