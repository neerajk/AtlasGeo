"""Auto-discovers and loads all tool.py files from the tools/ directory."""

import importlib.util
import sys
from pathlib import Path


def load_all_tools(tools_dir: Path | None = None) -> list[str]:
    """Load all tools from tools/ directory. Returns list of loaded tool names."""
    if tools_dir is None:
        # tools/ is always at project root, two levels up from src/atlas/tools/
        tools_dir = Path(__file__).parent.parent.parent.parent / "tools"

    if not tools_dir.exists():
        return []

    loaded = []
    for tool_dir in sorted(tools_dir.iterdir()):
        if not tool_dir.is_dir() or tool_dir.name.startswith("_"):
            continue
        tool_file = tool_dir / "tool.py"
        if not tool_file.exists():
            continue

        module_name = f"atlas_contrib_tools.{tool_dir.name}"
        if module_name in sys.modules:
            loaded.append(tool_dir.name)
            continue

        spec = importlib.util.spec_from_file_location(module_name, tool_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                loaded.append(tool_dir.name)
            except Exception as e:
                print(f"[atlas] warning: failed to load tool {tool_dir.name}: {e}")

    return loaded
