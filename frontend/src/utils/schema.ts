import type { FormFieldExtended } from '@/types';

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
  return {
    name: f.name || f.key || '',
    label: f.label || f.name || '',
    type: f.type || 'text',
    required: f.required ?? false,
    default: f.default,
    color: f.color,
    sample: f.sample,
    options: f.options,
    formula: f.formula,
    base_field: f.base_field,
    days_field: f.days_field,
    is_quantity: f.is_quantity,
    description: f.description,
  };
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
