"""Acceso a la base de datos.

Se usa SQLite para que el proyecto corra sin instalar nada. Las consultas están en la carpeta sql/
y son SQL estándar: para SQL Server alcanza con cambiar `conectar()` por una conexión de pyodbc.
"""
import sqlite3
from pathlib import Path

import pandas as pd

SQL = Path(__file__).resolve().parent.parent / "sql"


def leer_sql(nombre: str) -> str:
    return (SQL / f"{nombre}.sql").read_text(encoding="utf-8")


def conectar(ruta: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def crear_esquema(con: sqlite3.Connection) -> None:
    con.executescript(leer_sql("esquema"))
    con.commit()


def facturas_pendientes(con: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(leer_sql("facturas_pendientes"), con)
    for col in ("fecha", "vencimiento"):
        df[col] = pd.to_datetime(df[col])
    return df


def resumen_por_cliente(con: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(leer_sql("resumen_por_cliente"), con)


def movimientos_registrados(con: sqlite3.Connection) -> set[str]:
    return {fila[0] for fila in con.execute("SELECT movimiento FROM cobros")}


def registrar_cobro(con: sqlite3.Connection, movimiento: str, numero: str, importe: float) -> bool:
    """Suma el cobro a la factura y actualiza su estado (cobrada si ya no queda saldo).

    Devuelve False si ese movimiento ya estaba registrado (no lo suma de nuevo).
    """
    nuevo = con.execute("INSERT OR IGNORE INTO cobros (movimiento, numero, importe) VALUES (?, ?, ?)",
                        (movimiento, numero, importe)).rowcount
    if not nuevo:
        return False
    con.execute(
        """
        UPDATE facturas
        SET cobrado = cobrado + ?,
            estado  = CASE WHEN cobrado + ? >= total - 0.01 THEN 'cobrada' ELSE 'parcial' END
        WHERE numero = ?
        """,
        (importe, importe, numero),
    )
    return True
