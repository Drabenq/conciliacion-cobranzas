"""Arma el Excel que recibe el área de Cobranzas."""
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

COLORES = {"conciliado": "C6EFCE", "pago parcial": "FFEB9C", "pago de más": "FFEB9C", "para revisar": "FFC7CE"}

ETIQUETAS = {
    "movimientos": "Movimientos del banco (cobros)",
    "conciliados": "Conciliados automáticamente",
    "pagos_parciales_o_de_mas": "Pagos parciales o de más",
    "para_revisar": "Para revisar a mano",
    "importe_conciliado": "Importe identificado ($)",
    "facturas_pendientes": "Facturas que siguen pendientes",
    "facturas_vencidas": "De esas, vencidas",
    "deuda_vencida": "Deuda vencida ($)",
    "segundos": "Tiempo del proceso (segundos)",
}


def _ajustar(hoja):
    hoja.freeze_panes = "A2"
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for i, col in enumerate(hoja.columns, start=1):
        ancho = max(len(str(c.value or "")) for c in col)
        hoja.column_dimensions[get_column_letter(i)].width = min(ancho + 2, 60)


def generar_excel(ruta: str | Path, resumen: dict, movimientos: pd.DataFrame,
                  pendientes: pd.DataFrame, por_cliente: pd.DataFrame) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cols = ["fecha", "descripcion", "importe", "estado", "factura", "cliente", "diferencia", "regla"]
    mov = movimientos[cols].copy()
    mov["fecha"] = mov["fecha"].dt.date
    pend = pendientes[["numero", "cliente", "cuit", "fecha", "vencimiento", "total", "saldo"]].copy()
    for c in ("fecha", "vencimiento"):
        pend[c] = pend[c].dt.date

    with pd.ExcelWriter(ruta, engine="openpyxl") as xl:
        pd.DataFrame({"Indicador": [ETIQUETAS.get(k, k) for k in resumen], "Valor": list(resumen.values())}
                     ).to_excel(xl, sheet_name="Resumen", index=False)
        mov[mov["estado"] != "conciliado"].to_excel(xl, sheet_name="Para revisar", index=False)
        mov.to_excel(xl, sheet_name="Movimientos", index=False)
        pend.to_excel(xl, sheet_name="Facturas pendientes", index=False)
        por_cliente.to_excel(xl, sheet_name="Deuda por cliente", index=False)

        for hoja in xl.book.worksheets:
            _ajustar(hoja)
        for nombre in ("Para revisar", "Movimientos"):
            hoja = xl.book[nombre]
            col_estado = cols.index("estado") + 1
            for fila in hoja.iter_rows(min_row=2):
                color = COLORES.get(fila[col_estado - 1].value)
                if color:
                    for c in fila:
                        c.fill = PatternFill("solid", fgColor=color)
    return ruta
