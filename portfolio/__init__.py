"""Resume/portfolio site + JD-variant generator.

``main.py`` at the repo root is a thin shim over :func:`portfolio.cli.main`; all
logic lives in this package. Every legacy CLI flag (``--variant``,
``--new-variant``, ``--list-variants``, ``--all-variants``, ``--insights``, and
bare invocation) is preserved by ``portfolio.cli``.

The package carries no module-level filesystem globals: a :class:`portfolio.paths.Paths`
instance is threaded through every function so the whole pipeline can run against
a temporary directory (used by the tests) without monkeypatching.
"""
