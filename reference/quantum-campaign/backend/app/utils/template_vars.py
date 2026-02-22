"""템플릿 변수 치환 유틸리티."""

import re
from typing import Any, Dict, List, Optional, Tuple


# 변수명 매핑 (한글 변수명 → context 키)
VARIABLE_MAP = {
    "명소명": "landmark_name",
    "상호명": "place_name",
    "걸음수": "steps",
    "출발지": "landmark_name",  # 명소명 별칭
    "목적지": "place_name",  # 상호명 별칭
    "명소순번": "landmark_index",  # N번째 명소 (1-based)
}

# 변수 패턴 (예: &명소명&, &상호명&, &걸음수&)
VARIABLE_PATTERN = re.compile(r"&([^&]+)&")


def apply_template_variables(
    template_text: str,
    context: Dict[str, Any],
    strict: bool = False,
) -> str:
    """템플릿 텍스트에서 &변수명& 형태를 실제 값으로 치환.

    Args:
        template_text: 변수가 포함된 템플릿 텍스트
        context: 변수 값을 담은 컨텍스트 딕셔너리
        strict: True면 치환되지 않은 변수가 있을 때 예외 발생

    Returns:
        치환된 텍스트

    Raises:
        ValueError: strict=True이고 치환되지 않은 변수가 있을 때

    Examples:
        >>> context = {
        ...     "landmark_name": "마포역 2번출구",
        ...     "place_name": "일류곱창 마포공덕본점",
        ...     "steps": 863
        ... }
        >>> template = "&명소명&에서 &상호명&까지 &걸음수& 걸음"
        >>> apply_template_variables(template, context)
        '마포역 2번출구에서 일류곱창 마포공덕본점까지 863 걸음'
    """
    if not template_text:
        return template_text

    result = template_text
    unmatched_vars = []

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1)

        # 한글 변수명을 context 키로 변환
        context_key = VARIABLE_MAP.get(var_name, var_name)

        # context에서 값 조회
        value = context.get(context_key)

        if value is not None:
            return str(value)
        else:
            unmatched_vars.append(var_name)
            return match.group(0)  # 원본 유지

    result = VARIABLE_PATTERN.sub(replace_var, result)

    if strict and unmatched_vars:
        raise ValueError(f"치환되지 않은 변수가 있습니다: {unmatched_vars}")

    return result


def extract_variables(template_text: str) -> List[str]:
    """템플릿 텍스트에서 변수명 목록 추출.

    Args:
        template_text: 변수가 포함된 템플릿 텍스트

    Returns:
        변수명 목록 (중복 제거)

    Examples:
        >>> template = "&명소명&에서 &상호명&까지 &걸음수& 걸음"
        >>> extract_variables(template)
        ['명소명', '상호명', '걸음수']
    """
    if not template_text:
        return []

    matches = VARIABLE_PATTERN.findall(template_text)
    # 중복 제거하면서 순서 유지
    seen = set()
    result = []
    for var in matches:
        if var not in seen:
            seen.add(var)
            result.append(var)
    return result


def validate_template_variables(
    template_text: str,
    available_variables: List[str],
) -> Tuple[bool, List[str]]:
    """템플릿의 변수가 사용 가능한 변수 목록에 포함되는지 검증.

    Args:
        template_text: 변수가 포함된 템플릿 텍스트
        available_variables: 사용 가능한 변수명 목록 (한글 또는 영문)

    Returns:
        (유효 여부, 유효하지 않은 변수 목록) 튜플

    Examples:
        >>> template = "&명소명&에서 &상호명&까지"
        >>> validate_template_variables(template, ["명소명", "상호명"])
        (True, [])
        >>> validate_template_variables(template, ["명소명"])
        (False, ['상호명'])
    """
    used_vars = extract_variables(template_text)

    # 영문 키도 허용
    available_set = set(available_variables)
    for eng_key in available_variables:
        # VARIABLE_MAP의 역방향 조회
        for kor_key, val in VARIABLE_MAP.items():
            if val == eng_key:
                available_set.add(kor_key)

    invalid_vars = [var for var in used_vars if var not in available_set]

    return (len(invalid_vars) == 0, invalid_vars)


def get_available_variables_for_modules(module_ids: List[str]) -> List[str]:
    """모듈 ID 목록에서 사용 가능한 변수명 목록 반환.

    Args:
        module_ids: 모듈 ID 목록

    Returns:
        사용 가능한 변수명 목록 (한글)
    """
    from app.modules.registry import ModuleRegistry

    available_vars = []

    for module_id in module_ids:
        module = ModuleRegistry.get(module_id)
        if module:
            for output_var in module.output_variables:
                # 영문 키를 한글로 변환
                for kor_key, eng_key in VARIABLE_MAP.items():
                    if eng_key == output_var and kor_key not in available_vars:
                        available_vars.append(kor_key)

    # 기본 변수 추가 (상호명은 항상 사용 가능)
    if "상호명" not in available_vars:
        available_vars.append("상호명")

    return available_vars
