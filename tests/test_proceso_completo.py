import pandas as pd

from conciliacion import db
from conciliacion.__main__ import main


def test_de_punta_a_punta(datos, tmp_path):
    base, salida = tmp_path / "cobranzas.db", tmp_path / "salida"
    args = ["--datos", str(datos), "--base", str(base), "--salida", str(salida)]
    main(args + ["cargar"])
    main(args + ["conciliar", "--registrar", "--fecha-corte", "2026-11-16"])

    hojas = pd.read_excel(salida / "conciliacion.xlsx", sheet_name=None)
    assert set(hojas) == {"Resumen", "Para revisar", "Movimientos", "Facturas pendientes", "Deuda por cliente"}
    mov = hojas["Movimientos"]
    assert (mov["estado"] == "conciliado").sum() >= 15
    assert mov["descripcion"].str.contains("CLIENTE SIN DATOS").any()
    assert mov.loc[mov["descripcion"].str.contains("CLIENTE SIN DATOS"), "estado"].item() == "para revisar"

    # La base quedó actualizada: lo conciliado figura como cobrado y los pagos parciales como "parcial"
    con = db.conectar(base)
    estados = dict(con.execute("SELECT estado, COUNT(*) FROM facturas GROUP BY estado").fetchall())
    assert estados["cobrada"] >= 15 and estados["parcial"] == 3
    assert len(db.facturas_pendientes(con)) == len(hojas["Facturas pendientes"]) + 3


def test_correr_dos_veces_no_cuenta_doble(datos, tmp_path):
    base, salida = tmp_path / "cobranzas.db", tmp_path / "salida"
    args = ["--datos", str(datos), "--base", str(base), "--salida", str(salida)]
    main(args + ["cargar"])
    main(args + ["conciliar", "--registrar", "--fecha-corte", "2026-11-16"])
    con = db.conectar(base)
    antes = con.execute("SELECT SUM(cobrado) FROM facturas").fetchone()[0]
    main(args + ["conciliar", "--registrar", "--fecha-corte", "2026-11-16"])
    assert con.execute("SELECT SUM(cobrado) FROM facturas").fetchone()[0] == antes
