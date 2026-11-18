# Conciliación automática de cobranzas

![Tests](https://github.com/Drabenq/conciliacion-cobranzas/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-4479A1?logo=sqlite&logoColor=white)

Todos los días alguien de Cobranzas abre el extracto del banco, mira cada transferencia, busca a qué factura
corresponde y la marca como cobrada. Este proyecto hace ese trabajo solo:

1. **Lee las facturas en PDF** y carga sus datos en una base SQL. Usa reglas (expresiones regulares) y, si una
   factura viene en un formato que las reglas no entienden, se la pasa a un **modelo de IA** (Claude) para que
   devuelva los datos en JSON.
2. **Cruza el extracto bancario (CSV) contra las facturas pendientes** con pandas.
3. **Arma un Excel** con lo conciliado, lo que hay que revisar a mano, la deuda vencida y la deuda por cliente.
4. **Actualiza la base** marcando las facturas cobradas o con pago parcial.

> Los datos son de ejemplo: empresas, CUIT e importes inventados, generados por `conciliacion/generar.py`.

## Resultado con los datos de ejemplo

```
$ python -m conciliacion todo --fecha-corte 2026-11-16
✔ 24 facturas cargadas (0 leídas con IA)
  Movimientos del banco (cobros)       21
  Conciliados automáticamente          16
  Pagos parciales o de más             4
  Para revisar a mano                  1
  Importe identificado ($)             6729411.0
  Facturas que siguen pendientes       4
  De esas, vencidas                    2
  Deuda vencida ($)                    687764.0
  Tiempo del proceso (segundos)        0.04
✔ Reporte: salida/conciliacion.xlsx
```

De 21 cobros, **20 se identifican solos** y solo 1 queda para que lo mire una persona.

### Cuánto tiempo libera

Suponiendo unos 3 minutos por cobro conciliado a mano (buscar la transferencia, encontrar la factura, marcarla)
y 300 cobros por mes, son **unas 15 horas por mes**. Con el proceso, la persona solo revisa la hoja
"Para revisar" del Excel: en el ejemplo, 5 % de los movimientos.

## Cómo concilia

Cada cobro se asigna con la primera regla que lo identifica, y una factura nunca se asigna dos veces:

| Regla | Ejemplo de descripción en el banco | Cuándo se aplica |
|---|---|---|
| 1 · Número de factura | `TRANSF RECIBIDA ... PAGO FC 0001-00001208` | El número aparece en la descripción (con o sin guion) |
| 2 · CUIT + importe | `CREDITO TRANSF CUIT 30704441115 VARIOS` | Hay **una sola** factura de ese CUIT por ese importe |
| 3 · Importe único | `DEPOSITO EN EFECTIVO SUC 123` | Sin datos, pero hay **una sola** factura pendiente por ese importe |

Si hay dos facturas posibles, **no adivina**: el movimiento queda "para revisar". Además distingue pagos
parciales y pagos de más (con la diferencia en pesos), e ignora los débitos (comisiones, impuestos).

## Estructura

```
conciliacion/
  extractor.py    # PDF → datos de la factura (reglas, y si no alcanzan, IA)
  db.py           # conexión y consultas a la base
  conciliar.py    # las 3 reglas de cruce, con pandas
  reporte.py      # Excel con colores: verde conciliado, amarillo parcial, rojo para revisar
  generar.py      # datos de ejemplo (facturas PDF con reportlab y extracto CSV)
  __main__.py     # línea de comandos
sql/              # las consultas SQL, separadas del código
tests/            # 21 tests con pytest (la IA se prueba con una respuesta simulada, sin gastar)
```

## Correrlo

```bash
git clone https://github.com/Drabenq/conciliacion-cobranzas
cd conciliacion-cobranzas
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m conciliacion todo        # genera los datos de ejemplo, carga facturas, concilia y arma el Excel
python -m pytest -q                # tests
```

Por pasos: `ejemplo` (datos de prueba), `cargar` (PDF → base), `conciliar` (extracto vs base → Excel).
Con `conciliar --registrar` también marca las facturas como cobradas en la base. Se puede correr
varias veces con el mismo extracto: los movimientos ya registrados se saltean (tabla `cobros`).

**IA para facturas con otro formato:** definí la variable `ANTHROPIC_API_KEY` y el extractor la usa solo
cuando las reglas no encuentran todos los datos. Sin la clave, esas facturas se informan como "no leídas"
y el resto del proceso sigue igual.

## Para usarlo en una empresa

- **SQL Server:** las consultas de `sql/` son SQL estándar. Alcanza con cambiar `db.conectar()` por una
  conexión de `pyodbc` a la base del sistema de gestión, en vez de la base SQLite de ejemplo.
- **Formato del banco:** `leer_extracto()` espera `fecha;descripcion;importe`. Cada banco exporta distinto,
  así que se adapta esa función.
- **Que corra solo:** con el Programador de tareas de Windows o con cron en Linux, por ejemplo todos los días
  a las 8:00, y el Excel queda listo cuando llega el equipo:
  ```
  0 8 * * 1-5  cd /ruta/conciliacion-cobranzas && .venv/bin/python -m conciliacion conciliar --registrar
  ```

## Stack

Python 3.12 · pandas · SQL (SQLite / SQL Server) · openpyxl · pdfplumber · reportlab · API de Claude · pytest · GitHub Actions
