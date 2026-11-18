import pandas as pd
import pytest

from conciliacion.conciliar import conciliar, resumen


@pytest.fixture
def pendientes():
    return pd.DataFrame([
        {"numero": "0001-00000001", "cliente": "A", "cuit": "30-11111111-1", "saldo": 1000.0,
         "vencimiento": pd.Timestamp("2026-10-01")},
        {"numero": "0001-00000002", "cliente": "B", "cuit": "30-22222222-2", "saldo": 2500.0,
         "vencimiento": pd.Timestamp("2026-12-01")},
        {"numero": "0001-00000003", "cliente": "B", "cuit": "30-22222222-2", "saldo": 700.0,
         "vencimiento": pd.Timestamp("2026-10-15")},
        {"numero": "0001-00000004", "cliente": "C", "cuit": "30-33333333-3", "saldo": 700.0,
         "vencimiento": pd.Timestamp("2026-12-01")},
    ])


def extracto(*filas):
    return pd.DataFrame([{"fecha": pd.Timestamp("2026-11-10"), "descripcion": d, "importe": i} for d, i in filas])


def estado_de(resultado, descripcion):
    return resultado.set_index("descripcion").loc[descripcion]


def test_regla_1_numero_de_factura(pendientes):
    mov, siguen = conciliar(extracto(("PAGO FC 0001-00000001", 1000.0)), pendientes)
    fila = estado_de(mov, "PAGO FC 0001-00000001")
    assert (fila["factura"], fila["estado"], fila["regla"]) == ("0001-00000001", "conciliado", "1 · número de factura")
    assert "0001-00000001" not in siguen["numero"].values


def test_regla_1_acepta_numero_sin_guion(pendientes):
    mov, _ = conciliar(extracto(("TRANSF FC 000100000002", 2500.0)), pendientes)
    assert mov.loc[0, "factura"] == "0001-00000002"


def test_regla_2_cuit_e_importe(pendientes):
    mov, _ = conciliar(extracto(("TRANSF CUIT 30222222222", 2500.0)), pendientes)
    assert (mov.loc[0, "factura"], mov.loc[0, "regla"]) == ("0001-00000002", "2 · CUIT + importe")


def test_regla_3_importe_unico(pendientes):
    mov, _ = conciliar(extracto(("DEPOSITO EFECTIVO", 1000.0)), pendientes)
    assert (mov.loc[0, "factura"], mov.loc[0, "regla"]) == ("0001-00000001", "3 · importe único")


def test_importe_repetido_sin_datos_queda_para_revisar(pendientes):
    """Hay dos facturas de 700: el bot no adivina, se lo deja a una persona."""
    mov, _ = conciliar(extracto(("DEPOSITO EFECTIVO", 700.0)), pendientes)
    assert mov.loc[0, "estado"] == "para revisar" and pd.isna(mov.loc[0, "factura"])


def test_con_cuit_desempata_importes_repetidos(pendientes):
    mov, _ = conciliar(extracto(("TRANSF CUIT 30-33333333-3", 700.0)), pendientes)
    assert mov.loc[0, "factura"] == "0001-00000004"


def test_pago_parcial_y_pago_de_mas(pendientes):
    mov, _ = conciliar(extracto(("A CUENTA FC 0001-00000002", 1000.0), ("FC 0001-00000001 Y OTROS", 1200.0)), pendientes)
    assert estado_de(mov, "A CUENTA FC 0001-00000002")["estado"] == "pago parcial"
    fila = estado_de(mov, "FC 0001-00000001 Y OTROS")
    assert (fila["estado"], fila["diferencia"]) == ("pago de más", 200.0)


def test_una_factura_no_se_asigna_dos_veces(pendientes):
    mov, _ = conciliar(extracto(("FC 0001-00000001", 1000.0), ("DEPOSITO", 1000.0)), pendientes)
    assert mov["factura"].tolist().count("0001-00000001") == 1
    assert estado_de(mov, "DEPOSITO")["estado"] == "para revisar"


def test_debitos_no_se_concilian(pendientes):
    mov, _ = conciliar(extracto(("COMISION BANCARIA", -1500.0), ("FC 0001-00000001", 1000.0)), pendientes)
    assert len(mov) == 1


def test_resumen_cuenta_vencidas(pendientes):
    mov, siguen = conciliar(extracto(("FC 0001-00000001", 1000.0)), pendientes)
    r = resumen(mov, siguen, "2026-11-16")
    assert r["conciliados"] == 1 and r["facturas_pendientes"] == 3
    assert r["facturas_vencidas"] == 1 and r["deuda_vencida"] == 700.0
