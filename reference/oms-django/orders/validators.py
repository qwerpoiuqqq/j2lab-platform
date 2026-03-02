import pandas as pd
from datetime import datetime


def validate_order_data(rows, schema):
    """
    rows: list of dicts from Handsontable grid
    schema: product schema (list of field definitions)
    Returns: (valid_rows, errors)
    """
    if not rows:
        return [], [{'row': 0, 'message': '데이터가 없습니다.'}]

    df = pd.DataFrame(rows)
    errors = []
    # readonly/calc 필드 제외
    editable_schema = [f for f in schema if f.get('type') not in ('readonly', 'calc', 'date_calc')]
    required_fields = [f for f in editable_schema if f.get('required', False)]

    for idx, row in df.iterrows():
        row_num = idx + 1
        for field in required_fields:
            field_name = field['name']
            value = row.get(field_name, '')
            if pd.isna(value) or str(value).strip() == '':
                errors.append({
                    'row': row_num,
                    'field': field_name,
                    'message': f'{field.get("label", field_name)} 값이 비어있습니다.',
                })

        # URL 필드 기본 검증
        for field in editable_schema:
            if field.get('type') == 'url':
                value = str(row.get(field['name'], '')).strip()
                if value and not (value.startswith('http://') or value.startswith('https://')):
                    errors.append({
                        'row': row_num,
                        'field': field['name'],
                        'message': f'{field.get("label", field["name"])}은(는) http:// 또는 https://로 시작해야 합니다.',
                    })

        # 숫자 필드 검증
        for field in editable_schema:
            if field.get('type') == 'number':
                value = row.get(field['name'], '')
                if value and not pd.isna(value):
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        errors.append({
                            'row': row_num,
                            'field': field['name'],
                            'message': f'{field.get("label", field["name"])}은(는) 숫자여야 합니다.',
                        })

        # 날짜 필드 검증
        for field in editable_schema:
            if field.get('type') == 'date':
                value = str(row.get(field['name'], '')).strip()
                if value:
                    try:
                        datetime.strptime(value, '%Y-%m-%d')
                    except ValueError:
                        errors.append({
                            'row': row_num,
                            'field': field['name'],
                            'message': f'{field.get("label", field["name"])}은(는) YYYY-MM-DD 형식이어야 합니다.',
                        })

    # 빈 행 제거
    valid_rows = []
    for row in rows:
        if any(str(v).strip() for v in row.values() if v is not None):
            valid_rows.append(row)

    return valid_rows, errors
