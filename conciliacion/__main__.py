"""Uso:
    python -m conciliacion ejemplo            # genera facturas PDF y extracto de ejemplo en datos/
    python -m conciliacion cargar             # lee los PDF y carga las facturas en la base
    python -m conciliacion conciliar          # cruza el extracto con la base y arma el Excel
    python -m conciliacion conciliar --registrar   # además marca en la base lo que se cobró
    python -m conciliacion todo               # los tres pasos de una
"""
import argparse
import sys
import time
from datetime import date
from pathlib import Path

from . import db, extractor, generar
from .conciliar import conciliar, leer_extracto, resumen
from .reporte import ETIQUETAS, generar_excel


def cmd_ejemplo(a):
    r = generar.generar(a.datos)
    print(f"✔ {r['facturas']} facturas PDF y {r['movimientos']} movimientos en {a.datos}/")


def cmd_cargar(a):
    con = db.conectar(a.base)
    db.crear_esquema(con)
    ok, errores, con_ia = 0, [], 0
    for pdf in sorted(Path(a.datos, "facturas").glob("*.pdf")):
        try:
            f = extractor.leer_factura(pdf)
        except extractor.FacturaIlegible as e:
            errores.append(str(e))
            continue
        con.execute("INSERT OR IGNORE INTO clientes (razon_social, cuit) VALUES (?, ?)", (f.cliente, f.cuit))
        cid = con.execute("SELECT id FROM clientes WHERE cuit = ?", (f.cuit,)).fetchone()[0]
        vto = date.fromisoformat(f.fecha).toordinal() + a.dias_vencimiento
        con.execute(
            "INSERT OR IGNORE INTO facturas (numero, cliente_id, fecha, vencimiento, total) VALUES (?, ?, ?, ?, ?)",
            (f.numero, cid, f.fecha, date.fromordinal(vto).isoformat(), f.total),
        )
        ok += 1
        con_ia += f.metodo == "ia"
    con.commit()
    print(f"✔ {ok} facturas cargadas ({con_ia} leídas con IA)")
    for e in errores:
        print(f"  ✘ {e}")


def cmd_conciliar(a):
    inicio = time.perf_counter()
    if not Path(a.base).exists():
        sys.exit(f"✘ No existe la base {a.base}: primero corré  python -m conciliacion cargar")
    con = db.conectar(a.base)
    db.crear_esquema(con)
    pendientes = db.facturas_pendientes(con)
    extracto = leer_extracto(Path(a.datos, "extracto_banco.csv"))
    ya = db.movimientos_registrados(con)
    if ya:
        print(f"  ({extracto['id'].isin(ya).sum()} movimientos ya estaban registrados de una corrida anterior)")
        extracto = extracto[~extracto["id"].isin(ya)]
    movimientos, siguen = conciliar(extracto, pendientes)
    if a.registrar:
        for _, m in movimientos[movimientos["factura"].notna()].iterrows():
            db.registrar_cobro(con, m["id"], m["factura"], m["importe"])
        con.commit()
    res = resumen(movimientos, siguen, a.fecha_corte)
    res["segundos"] = round(time.perf_counter() - inicio, 2)
    ruta = generar_excel(Path(a.salida, "conciliacion.xlsx"), res, movimientos, siguen, db.resumen_por_cliente(con))
    for k, v in res.items():
        print(f"  {ETIQUETAS[k]:<36} {v}")
    print(f"✔ Reporte: {ruta}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="conciliacion", description="Conciliación automática de cobranzas")
    p.add_argument("--datos", default="datos")
    p.add_argument("--base", default="salida/cobranzas.db")
    p.add_argument("--salida", default="salida")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ejemplo")
    c = sub.add_parser("cargar")
    c.add_argument("--dias-vencimiento", type=int, default=30)
    for nombre in ("conciliar", "todo"):
        s = sub.add_parser(nombre)
        s.add_argument("--registrar", action="store_true", help="marcar en la base las facturas cobradas")
        s.add_argument("--fecha-corte", default=date.today().isoformat())
        s.add_argument("--dias-vencimiento", type=int, default=30)
    a = p.parse_args(argv)
    Path(a.base).parent.mkdir(parents=True, exist_ok=True)
    if a.cmd == "todo":
        if not Path(a.datos, "extracto_banco.csv").exists():
            cmd_ejemplo(a)
        cmd_cargar(a)
        cmd_conciliar(a)
    else:
        {"ejemplo": cmd_ejemplo, "cargar": cmd_cargar, "conciliar": cmd_conciliar}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
