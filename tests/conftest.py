import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from conciliacion import generar  # noqa: E402


@pytest.fixture(scope="session")
def datos(tmp_path_factory):
    """Genera una vez los datos de ejemplo (PDF + extracto) en una carpeta temporal."""
    carpeta = tmp_path_factory.mktemp("datos")
    generar.generar(carpeta)
    return carpeta
