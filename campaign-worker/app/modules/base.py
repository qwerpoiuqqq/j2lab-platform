"""Module base class definition.

All campaign setup modules inherit from BaseModule.
Developers implement new modules; users toggle them on/off via templates.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ModuleError(Exception):
    """Error during module execution."""


class BaseModule(ABC):
    """Abstract base class for all campaign setup modules.

    Attributes:
        module_id: Unique module identifier (referenced in templates).
        description: Module description (for UI display).
        output_variables: List of variable names this module produces.
        dependencies: List of module IDs that must run before this one.
    """

    module_id: str = ""
    description: str = ""
    output_variables: List[str] = []
    dependencies: List[str] = []

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the module.

        Args:
            context: Input data dict (place_url, place_name, previous module results).

        Returns:
            Dict of output_variables with their values.

        Raises:
            ModuleError: On execution failure.
        """

    def get_info(self) -> Dict[str, Any]:
        """Return module metadata."""
        return {
            "module_id": self.module_id,
            "description": self.description,
            "output_variables": self.output_variables,
            "dependencies": self.dependencies,
        }

    def validate_context(self, context: Dict[str, Any], required_keys: List[str]) -> None:
        """Validate that context contains required keys."""
        missing = [k for k in required_keys if k not in context]
        if missing:
            raise ModuleError(
                f"Module '{self.module_id}' missing required data: {missing}"
            )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.module_id})>"
