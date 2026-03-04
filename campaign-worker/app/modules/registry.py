"""Module registry - registration and dependency-ordered execution.

Uses Kahn's algorithm for topological sort of module dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.modules.base import BaseModule, ModuleError

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Module registry: registers modules and executes them in dependency order."""

    _modules: Dict[str, BaseModule] = {}

    @classmethod
    def register(cls, module: BaseModule) -> None:
        cls._modules[module.module_id] = module
        logger.debug(f"Module registered: {module.module_id}")

    @classmethod
    def unregister(cls, module_id: str) -> None:
        cls._modules.pop(module_id, None)

    @classmethod
    def clear(cls) -> None:
        cls._modules.clear()

    @classmethod
    def get(cls, module_id: str) -> Optional[BaseModule]:
        return cls._modules.get(module_id)

    @classmethod
    def get_all(cls) -> List[BaseModule]:
        return list(cls._modules.values())

    @classmethod
    def get_all_info(cls) -> List[Dict[str, Any]]:
        return [m.get_info() for m in cls._modules.values()]

    @classmethod
    def _sort_by_dependencies(cls, module_ids: List[str]) -> List[str]:
        """Topological sort using Kahn's algorithm."""
        for mid in module_ids:
            if mid not in cls._modules:
                raise ModuleError(f"Unknown module: {mid}")

        in_degree: Dict[str, int] = {mid: 0 for mid in module_ids}
        graph: Dict[str, List[str]] = {mid: [] for mid in module_ids}

        for mid in module_ids:
            module = cls._modules[mid]
            for dep_id in module.dependencies:
                if dep_id in module_ids:
                    graph[dep_id].append(mid)
                    in_degree[mid] += 1

        queue = [mid for mid in module_ids if in_degree[mid] == 0]
        result: List[str] = []

        while queue:
            current = queue.pop(0)
            result.append(current)
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(module_ids):
            remaining = set(module_ids) - set(result)
            raise ModuleError(f"Circular dependency detected: {remaining}")

        return result

    @classmethod
    async def execute_modules(
        cls,
        module_ids: List[str],
        initial_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute modules in dependency order.

        Args:
            module_ids: List of module IDs to execute.
            initial_context: Initial data (place_url, place_name, etc.).

        Returns:
            Combined context dict with all module results.
        """
        if not module_ids:
            return initial_context.copy()

        sorted_modules = cls._sort_by_dependencies(module_ids)
        context = initial_context.copy()

        for module_id in sorted_modules:
            module = cls.get(module_id)
            if module is None:
                raise ModuleError(f"Unknown module: {module_id}")

            logger.info(f"Executing module: {module_id}")
            try:
                result = await module.execute(context)
                context.update(result)
                logger.info(f"Module {module_id} completed: {list(result.keys())}")
            except ModuleError:
                raise
            except Exception as e:
                raise ModuleError(f"Module '{module_id}' unexpected error: {str(e)}")

        return context


def register_default_modules() -> None:
    """Register default modules at application startup."""
    from app.modules.place_info import PlaceInfoModule
    from app.modules.landmark import LandmarkModule
    from app.modules.steps import StepsModule

    ModuleRegistry.register(PlaceInfoModule())
    ModuleRegistry.register(LandmarkModule())
    ModuleRegistry.register(StepsModule())
    logger.info(
        f"Default modules registered: {[m.module_id for m in ModuleRegistry.get_all()]}"
    )
