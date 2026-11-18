"""Cruza los movimientos del banco con las facturas pendientes.

Reglas, en orden (cada movimiento se concilia con la primera que lo identifica):
  1. El número de factura aparece en la descripción de la transferencia.
  2. El CUIT del cliente aparece en la descripción y hay UNA sola factura suya por ese importe.
  3. Sin CUIT ni número, pero hay UNA sola factura pendiente por exactamente ese importe.
Lo que no entra en ninguna regla queda "para revisar": eso es lo único que una persona tiene que mirar.
"""
import hashlib
import re

import pandas as pd

TOLERANCIA = 0.01  # diferencia máxima en pesos para considerar dos importes iguales

RE_FACTURA = re.compile(r"(\d{4,5})-?(\d{8})")
RE_CUIT = re.compile(r"\b(\d{2})-?(\d{8})-?(\d)\b")


def leer_extracto(ruta) -> pd.DataFrame:
    """CSV del banco: fecha;descripcion;importe (con ; y coma decimal, como exportan los bancos de acá)."""
    df = pd.read_csv(ruta, sep=";", decimal=",", thousands=".", dtype={"descripcion": str})
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True)
    df["id"] = [huella(f, d, i) for f, d, i in zip(df["fecha"], df["descripcion"], df["importe"])]
    return df


def huella(fecha, descripcion, importe) -> str:
    """Identificador estable de un movimiento, para no registrarlo dos veces."""
    return hashlib.sha1(f"{pd.Timestamp(fecha):%Y-%m-%d}|{descripcion}|{importe:.2f}".encode()).hexdigest()[:16]


def _numero_en(texto: str) -> str | None:
    m = RE_FACTURA.search(texto)
    return f"{int(m.group(1)):04d}-{m.group(2)}" if m else None


def _cuit_en(texto: str) -> str | None:
    m = RE_CUIT.search(texto)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _estado(importe: float, saldo: float) -> str:
    if abs(importe - saldo) <= TOLERANCIA:
        return "conciliado"
    return "pago parcial" if importe < saldo else "pago de más"


def conciliar(extracto: pd.DataFrame, pendientes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (movimientos con su resultado, facturas que siguen pendientes)."""
    cobros = extracto[extracto["importe"] > 0].copy()
    cobros["numero_detectado"] = cobros["descripcion"].map(_numero_en)
    cobros["cuit_detectado"] = cobros["descripcion"].map(_cuit_en)
    cobros[["factura", "cliente", "regla", "estado", "diferencia"]] = None

    libres = pendientes.set_index("numero").copy()   # facturas todavía sin asignar

    def asignar(i, numero, regla):
        fac = libres.loc[numero]
        importe = cobros.at[i, "importe"]
        cobros.loc[i, ["factura", "cliente", "regla"]] = [numero, fac["cliente"], regla]
        cobros.at[i, "estado"] = _estado(importe, fac["saldo"])
        cobros.at[i, "diferencia"] = round(importe - fac["saldo"], 2)
        libres.drop(numero, inplace=True)

    # Regla 1: número de factura en la descripción
    for i, numero in cobros["numero_detectado"].dropna().items():
        if numero in libres.index:
            asignar(i, numero, "1 · número de factura")

    # Reglas 2 y 3: por CUIT + importe, o solo por importe (siempre que haya un único candidato)
    for i in cobros.index[cobros["factura"].isna()]:
        importe = cobros.at[i, "importe"]
        mismo_importe = libres[(libres["saldo"] - importe).abs() <= TOLERANCIA]
        cuit = cobros.at[i, "cuit_detectado"]
        if pd.notna(cuit):
            candidatas = mismo_importe[mismo_importe["cuit"] == cuit]
            regla = "2 · CUIT + importe"
        else:
            candidatas = mismo_importe
            regla = "3 · importe único"
        if len(candidatas) == 1:
            asignar(i, candidatas.index[0], regla)

    cobros["estado"] = cobros["estado"].fillna("para revisar")
    return cobros.reset_index(drop=True), libres.reset_index()


def resumen(movimientos: pd.DataFrame, pendientes_finales: pd.DataFrame, fecha_corte) -> dict:
    vencidas = pendientes_finales[pendientes_finales["vencimiento"] < pd.Timestamp(fecha_corte)]
    return {
        "movimientos": len(movimientos),
        "conciliados": int((movimientos["estado"] == "conciliado").sum()),
        "pagos_parciales_o_de_mas": int(movimientos["estado"].isin(["pago parcial", "pago de más"]).sum()),
        "para_revisar": int((movimientos["estado"] == "para revisar").sum()),
        "importe_conciliado": round(float(movimientos.loc[movimientos["factura"].notna(), "importe"].sum()), 2),
        "facturas_pendientes": len(pendientes_finales),
        "facturas_vencidas": len(vencidas),
        "deuda_vencida": round(float(vencidas["saldo"].sum()), 2),
    }
