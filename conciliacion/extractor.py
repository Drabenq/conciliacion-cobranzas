"""Lee facturas en PDF y devuelve sus datos.

Primero intenta con reglas (expresiones regulares), que es rápido y gratis. Si una factura viene con un
formato distinto y las reglas no encuentran todos los campos, le pasa el texto a un modelo de IA (Claude)
y le pide los mismos datos en JSON. Así la IA solo se usa cuando hace falta.
"""
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pdfplumber
import requests

CAMPOS = ("numero", "cuit", "cliente", "fecha", "total")
API_URL = "https://api.anthropic.com/v1/messages"
MODELO = os.environ.get("MODELO_IA", "claude-haiku-5-5")


@dataclass
class Factura:
    numero: str
    cuit: str
    cliente: str
    fecha: str      # AAAA-MM-DD
    total: float
    archivo: str = ""
    metodo: str = "reglas"   # reglas | ia


class FacturaIlegible(Exception):
    pass


def importe_ar(texto: str) -> float:
    """'$ 1.234.567,89' -> 1234567.89"""
    limpio = re.sub(r"[^\d,.-]", "", texto)
    return float(limpio.replace(".", "").replace(",", "."))


def normalizar_cuit(texto: str) -> str:
    d = re.sub(r"\D", "", texto)
    return f"{d[:2]}-{d[2:10]}-{d[10:]}" if len(d) == 11 else texto


def fecha_iso(texto: str) -> str:
    """'05/10/2026' -> '2026-10-05'. Si ya viene en ISO, la deja igual."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", texto)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else texto


PATRONES = {
    "numero": r"N[°º]?\s*:?\s*(\d{4,5}-\d{8})",
    "cuit": r"CUIT(?:\s+cliente)?\s*:?\s*(\d{2}-?\d{8}-?\d)",
    "cliente": r"(?:Cliente|Señor(?:es)?|Razón social)\s*:\s*(.+)",
    "fecha": r"Fecha(?: de emisión)?\s*:\s*(\d{2}/\d{2}/\d{4})",
    "total": r"TOTAL\s*:?\s*\$?\s*([\d.]+,\d{2})",
}


def texto_pdf(ruta: str | Path) -> str:
    with pdfplumber.open(ruta) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def por_reglas(texto: str) -> dict:
    datos = {}
    for campo, patron in PATRONES.items():
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            datos[campo] = m.group(1).strip()
    return datos


def por_ia(texto: str, api_key: str, sesion=requests) -> dict:
    """Le pide a Claude los datos de la factura en JSON."""
    prompt = (
        "Extraé los datos de esta factura argentina. Respondé SOLO un JSON con las claves "
        '"numero" (formato 0001-00001234), "cuit" (del cliente, no del emisor), "cliente", '
        '"fecha" (DD/MM/AAAA) y "total" (como figura, ej. "1.234,56"). '
        "Si un dato no está, poné null.\n\n" + texto
    )
    r = sesion.post(
        API_URL,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODELO, "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    r.raise_for_status()
    respuesta = r.json()["content"][0]["text"]
    m = re.search(r"\{.*\}", respuesta, re.DOTALL)
    if not m:
        raise FacturaIlegible("La IA no devolvió un JSON")
    return {k: str(v) for k, v in json.loads(m.group(0)).items() if v not in (None, "")}


def armar(datos: dict, archivo: str, metodo: str) -> Factura:
    faltan = [c for c in CAMPOS if c not in datos]
    if faltan:
        raise FacturaIlegible(f"{archivo}: no se encontró {', '.join(faltan)}")
    return Factura(
        numero=datos["numero"],
        cuit=normalizar_cuit(datos["cuit"]),
        cliente=datos["cliente"],
        fecha=fecha_iso(datos["fecha"]),
        total=importe_ar(datos["total"]) if isinstance(datos["total"], str) else float(datos["total"]),
        archivo=archivo,
        metodo=metodo,
    )


def leer_factura(ruta: str | Path, api_key: str | None = None, sesion=requests) -> Factura:
    ruta = Path(ruta)
    texto = texto_pdf(ruta)
    datos = por_reglas(texto)
    if all(c in datos for c in CAMPOS):
        return armar(datos, ruta.name, "reglas")
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        faltan = ", ".join(c for c in CAMPOS if c not in datos)
        raise FacturaIlegible(f"{ruta.name}: las reglas no encontraron {faltan} y no hay ANTHROPIC_API_KEY para usar IA")
    return armar({**datos, **por_ia(texto, api_key, sesion)}, ruta.name, "ia")


def como_dict(f: Factura) -> dict:
    return asdict(f)
