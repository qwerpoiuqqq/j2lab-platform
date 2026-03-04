"""Template variable substitution utility.

Replaces template variables like &상호명&, &명소명& with actual values.
Ported from reference/quantum-campaign/backend/app/utils/template_vars.py.
"""

from __future__ import annotations

import re
from typing import Any, Dict


# Variable pattern: &variable_name& (Korean or English)
VARIABLE_PATTERN = re.compile(r"&([^&]+)&")

# Korean variable names -> context key mapping
KOREAN_VAR_MAP: dict[str, str] = {
    "상호명": "place_name",
    "명소명": "landmark_name",
    "명소순번": "landmark_index",
    "걸음수": "steps",
    "가게주소": "place_address",
}


def apply_template_variables(
    template: str,
    context: Dict[str, Any],
) -> str:
    """Replace template variables with values from context.

    Supports both Korean (&상호명&) and English (&place_name&) variable names.

    Args:
        template: Template string with &variable& placeholders.
        context: Dictionary of variable values.

    Returns:
        String with variables replaced.
    """
    if not template:
        return ""

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        # Try Korean mapping first
        key = KOREAN_VAR_MAP.get(var_name, var_name)
        value = context.get(key)
        if value is None:
            # Try the original variable name directly
            value = context.get(var_name)
        if value is None:
            return match.group(0)  # Keep original if not found
        return str(value)

    return VARIABLE_PATTERN.sub(replacer, template)
