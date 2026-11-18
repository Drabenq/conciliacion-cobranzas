"""Genera datos de ejemplo: facturas en PDF y un extracto bancario en CSV.

Empresas, CUIT e importes son inventados. El extracto incluye a propósito todos los casos que aparecen en
la vida real: transferencias con el número de factura, con el CUIT, sin nada, pagos parciales, pagos de más,
movimientos que no son cobros (comisiones, impuestos) y transferencias que nadie sabe de quién son.
"""
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

EMISOR = ("Distribuidora Ejemplo S.A.", "30-70000000-1")

CLIENTES = [
    ("Ferretería Los Andes S.R.L.", "30-71123456-2"),
    ("Constructora del Oeste S.A.", "30-70987654-3"),
    ("Electro Haedo S.R.L.", "30-71555222-9"),
    ("Instalaciones Morón S.A.", "30-70444111-5"),
    ("Taller Castelar de Juan Pérez", "20-28765432-1"),
    ("Corralón San Justo S.A.", "30-71222333-4"),
    ("Iluminación Ramos S.R.L.", "30-70888999-7"),
    ("Cooperativa Eléctrica Villa Sarmiento", "30-50011122-6"),
]


def _ar(importe: float) -> str:
    """1234567.8 -> '1.234.567,80'"""
    return f"{importe:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def factura_pdf(ruta: Path, numero: str, cliente: str, cuit: str, fecha: date, items: list[tuple]) -> float:
    c = canvas.Canvas(str(ruta), pagesize=A4)
    _, alto = A4
    y = alto - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, EMISOR[0])
    c.setFont("Helvetica", 10)
    c.drawString(50, y - 16, f"CUIT emisor: {EMISOR[1]}  ·  IVA Responsable Inscripto")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(380, y, f"FACTURA A  N° {numero}")
    c.setFont("Helvetica", 11)
    c.drawString(380, y - 18, f"Fecha: {fecha:%d/%m/%Y}")
    y -= 70
    c.drawString(50, y, f"Cliente: {cliente}")
    c.drawString(50, y - 16, f"CUIT cliente: {cuit}")
    y -= 50
    c.setFont("Helvetica-Bold", 10)
    for x, t in ((50, "Descripción"), (330, "Cant."), (390, "P. unit."), (480, "Importe")):
        c.drawString(x, y, t)
    c.setFont("Helvetica", 10)
    neto = 0.0
    for desc, cant, unit in items:
        y -= 16
        neto += cant * unit
        c.drawString(50, y, desc)
        c.drawString(330, y, str(cant))
        c.drawString(390, y, _ar(unit))
        c.drawString(480, y, _ar(cant * unit))
    iva = round(neto * 0.21, 2)
    total = round(neto + iva, 2)
    y -= 40
    c.drawString(390, y, "Neto gravado:")
    c.drawString(480, y, _ar(neto))
    c.drawString(390, y - 16, "IVA 21%:")
    c.drawString(480, y - 16, _ar(iva))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(390, y - 38, f"TOTAL: $ {_ar(total)}")
    c.save()
    return total


PRODUCTOS = [
    ("Cable unipolar 2,5 mm x 100 m", 48500.0), ("Térmica bipolar 32 A", 21300.0), ("Disyuntor 40 A", 58900.0),
    ("Caño corrugado 3/4 x 25 m", 9800.0), ("Tablero 12 bocas", 33400.0), ("Lámpara LED 12 W x 10", 15200.0),
    ("Toma doble con tierra", 4100.0), ("Reflector LED 100 W", 42700.0), ("Cinta aisladora x 10", 6900.0),
]


def generar(carpeta: str | Path, cantidad: int = 24, semilla: int = 7) -> dict:
    rnd = random.Random(semilla)
    carpeta = Path(carpeta)
    (carpeta / "facturas").mkdir(parents=True, exist_ok=True)
    hoy = date(2026, 11, 16)
    facturas = []
    for n in range(cantidad):
        cliente, cuit = CLIENTES[n % len(CLIENTES)]
        numero = f"0001-{1200 + n:08d}"
        fecha = hoy - timedelta(days=rnd.randint(5, 70))
        items = [(p, rnd.randint(1, 8), u) for p, u in rnd.sample(PRODUCTOS, rnd.randint(1, 4))]
        total = factura_pdf(carpeta / "facturas" / f"FC-A-{numero}.pdf", numero, cliente, cuit, fecha, items)
        facturas.append({"numero": numero, "cliente": cliente, "cuit": cuit, "fecha": fecha, "total": total})

    # Extracto bancario: cada factura cae en un caso distinto
    movs = []
    for i, f in enumerate(facturas):
        dia = min(f["fecha"] + timedelta(days=rnd.randint(1, 15)), hoy)
        caso = i % 8
        if caso in (0, 1, 2):     # transferencia con número de factura
            movs.append((dia, f"TRANSF RECIBIDA {f['cliente'][:18].upper()} PAGO FC {f['numero']}", f["total"]))
        elif caso in (3, 4):      # solo CUIT
            movs.append((dia, f"CREDITO TRANSF CUIT {f['cuit'].replace('-', '')} VARIOS", f["total"]))
        elif caso == 5:           # pago parcial con número
            movs.append((dia, f"TRANSF PAGO A CUENTA FC {f['numero']}", round(f["total"] * 0.5, 2)))
        elif caso == 6 and i < 8:  # depósito sin datos, pero el importe es único
            movs.append((dia, "DEPOSITO EN EFECTIVO SUC 123", f["total"]))
        # caso 7 (y el 6 a partir de la segunda vuelta): la factura no se pagó y queda pendiente
    movs += [
        (hoy - timedelta(days=3), "TRANSF RECIBIDA CLIENTE SIN DATOS", 87350.0),        # nadie sabe de quién es
        (hoy - timedelta(days=9), f"PAGO FC {facturas[7]['numero']} Y SALDO ANTERIOR",  # pago de más
         round(facturas[7]["total"] + 15000, 2)),
        (hoy - timedelta(days=2), "COMISION MANTENIMIENTO CUENTA", -18500.0),
        (hoy - timedelta(days=2), "IMP LEY 25413 DEB/CRED", -3120.45),
    ]
    movs.sort(key=lambda m: m[0])
    with open(carpeta / "extracto_banco.csv", "w", encoding="utf-8") as fh:
        fh.write("fecha;descripcion;importe\n")
        for dia, desc, imp in movs:
            fh.write(f"{dia:%d/%m/%Y};{desc};{_ar(imp)}\n")
    return {"facturas": len(facturas), "movimientos": len(movs), "fecha_corte": hoy}
