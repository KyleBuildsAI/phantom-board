"""
Adapter registry for Phantom Board.

Adapters bridge the gap between the abstract agent model and the
concrete runtime environment (Docker containers, local processes, etc.).
"""

from typing import Optional

from .base import BaseAdapter

_registry: dict[str, BaseAdapter] = {}


def register_adapter(name: str, adapter: BaseAdapter) -> None:
    """Register an adapter instance under a given name."""
    _registry[name] = adapter


def get_adapter(name: str) -> BaseAdapter:
    """Retrieve a registered adapter by name."""
    adapter = _registry.get(name)
    if adapter is None:
        # Lazy import and register defaults
        if name == "docker":
            from .docker_adapter import DockerAdapter
            adapter = DockerAdapter()
            register_adapter("docker", adapter)
        elif name == "process":
            from .process_adapter import ProcessAdapter
            adapter = ProcessAdapter()
            register_adapter("process", adapter)
        else:
            raise KeyError(f"Unknown adapter: {name}")
    return adapter


def list_adapters() -> list[str]:
    """Return names of all registered adapters."""
    return list(_registry.keys())


__all__ = ["BaseAdapter", "get_adapter", "register_adapter", "list_adapters"]
