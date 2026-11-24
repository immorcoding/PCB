# Tools

Two folders:

- `KiCadDesignTools/`: this workspace's own tools for schematics and boards (tracked here). A Python package: run each
  tool from the repository root as `python -m Tools.KiCadDesignTools.<category>.<tool>`; the build driver is
  `python -m Tools.KiCadDesignTools.build <board dir> <step>`. Index: [KiCadDesignTools/README.md](KiCadDesignTools/README.md).
- `KiCadRoutingTools/`: the third-party autorouter (its own git repository and venv, git-ignored; RTE-4: used by
  exception only). See `docs/tools.md`.

`Tools/` itself has no `__init__.py` (a namespace package) and no code of its own.
