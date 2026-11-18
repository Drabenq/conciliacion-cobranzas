import pytest

from conciliacion import extractor as ex


def test_lee_factura_pdf_con_reglas(datos):
    f = ex.leer_factura(datos / "facturas" / "FC-A-0001-00001204.pdf")
    assert f.numero == "0001-00001204"
    assert f.cuit == "20-28765432-1"
    assert f.cliente == "Taller Castelar de Juan Pérez"
    assert f.fecha.startswith("2026-")
    assert f.total > 0 and f.metodo == "reglas"


def test_todas_las_facturas_de_ejemplo_se_leen_sin_ia(datos):
    facturas = [ex.leer_factura(p) for p in sorted((datos / "facturas").glob("*.pdf"))]
    assert len(facturas) == 24
    assert all(f.metodo == "reglas" for f in facturas)


@pytest.mark.parametrize("texto, esperado", [
    ("$ 1.234.567,89", 1234567.89),
    ("12.523,50", 12523.5),
    ("4.961,00", 4961.0),
])
def test_importe_en_formato_argentino(texto, esperado):
    assert ex.importe_ar(texto) == esperado


def test_normaliza_cuit_y_fecha():
    assert ex.normalizar_cuit("30711234562") == "30-71123456-2"
    assert ex.fecha_iso("05/10/2026") == "2026-10-05"


class RespuestaFalsa:
    def __init__(self, texto):
        self.texto = texto

    def raise_for_status(self):
        pass

    def json(self):
        return {"content": [{"type": "text", "text": self.texto}]}


class SesionFalsa:
    """Reemplaza a requests para no llamar a la API real en los tests."""
    def __init__(self, texto):
        self.texto, self.pedidos = texto, []

    def post(self, url, **kw):
        self.pedidos.append(kw["json"])
        return RespuestaFalsa(self.texto)


OTRO_FORMATO = """COMPROBANTE ELECTRÓNICO
Comprobante 0003-00045678 emitido el 2 de noviembre de 2026
Destinatario: Ferretería Los Andes S.R.L. (CUIT 30711234562)
Importe final a pagar 152.300,00 pesos"""


def test_si_las_reglas_no_alcanzan_usa_ia(monkeypatch, tmp_path):
    monkeypatch.setattr(ex, "texto_pdf", lambda ruta: OTRO_FORMATO)
    sesion = SesionFalsa('Acá están los datos: {"numero": "0003-00045678", "cuit": "30-71123456-2", '
                         '"cliente": "Ferretería Los Andes S.R.L.", "fecha": "02/11/2026", "total": "152.300,00"}')
    f = ex.leer_factura(tmp_path / "rara.pdf", api_key="clave-de-prueba", sesion=sesion)
    assert f.metodo == "ia"
    assert (f.numero, f.cuit, f.fecha, f.total) == ("0003-00045678", "30-71123456-2", "2026-11-02", 152300.0)
    assert "COMPROBANTE ELECTRÓNICO" in sesion.pedidos[0]["messages"][0]["content"]


def test_sin_clave_de_ia_avisa_que_campos_faltan(monkeypatch, tmp_path):
    monkeypatch.setattr(ex, "texto_pdf", lambda ruta: OTRO_FORMATO)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ex.FacturaIlegible, match="no hay ANTHROPIC_API_KEY"):
        ex.leer_factura(tmp_path / "rara.pdf")


def test_si_la_ia_no_devuelve_json_falla_claro(monkeypatch, tmp_path):
    monkeypatch.setattr(ex, "texto_pdf", lambda ruta: OTRO_FORMATO)
    with pytest.raises(ex.FacturaIlegible):
        ex.leer_factura(tmp_path / "rara.pdf", api_key="x", sesion=SesionFalsa("No pude leerla"))
