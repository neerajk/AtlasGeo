"""
@atlas_tool decorator.

Contributor usage:
    from atlas.tools import atlas_tool

    @atlas_tool(name="my_tool", description="...", tags=["sentinel-2"])
    def my_tool(param: str) -> dict:
        ...

That's all. Tool auto-registers and becomes available to all agents.
"""

from __future__ import annotations

from typing import Any, Callable
from langchain_core.tools import StructuredTool

TOOL_REGISTRY: dict[str, "AtlasTool"] = {}


class AtlasTool:
    def __init__(self, fn: Callable, name: str, description: str, tags: list[str]):
        self.fn = fn
        self.name = name
        self.description = description
        self.tags = tags
        self._langchain_tool: StructuredTool | None = None

    def as_langchain_tool(self) -> StructuredTool:
        if self._langchain_tool is None:
            self._langchain_tool = StructuredTool.from_function(
                func=self.fn,
                name=self.name,
                description=self.description,
            )
        return self._langchain_tool

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<AtlasTool name={self.name!r} tags={self.tags}>"


def atlas_tool(name: str, description: str, tags: list[str] | None = None):
    """Decorator that registers a function as an Atlas tool."""
    def decorator(fn: Callable) -> AtlasTool:
        tool = AtlasTool(fn, name, description, tags or [])
        TOOL_REGISTRY[name] = tool
        return tool
    return decorator


def get_all_langchain_tools(tags: list[str] | None = None) -> list[StructuredTool]:
    """Return all registered tools as LangChain StructuredTools, optionally filtered by tag."""
    tools = TOOL_REGISTRY.values()
    if tags:
        tools = [t for t in tools if any(tag in t.tags for tag in tags)]
    return [t.as_langchain_tool() for t in tools]
