"""Module system package.

Provides modules for collecting campaign registration data:
- place_info: Extract real place name and address
- landmark: Select nearby landmark
- steps: Calculate walking steps
"""

from app.modules.base import BaseModule, ModuleError
from app.modules.registry import ModuleRegistry

__all__ = [
    "BaseModule",
    "ModuleError",
    "ModuleRegistry",
]
