"""The package is importable from a bare checkout.

Thin on purpose, and not a placeholder: it is what proves the layout plus the pytest
`pythonpath` setting agree, so the first real test does not have to debug both at once.
"""

import grimoire


def test_version_is_exposed() -> None:
    assert grimoire.__version__
