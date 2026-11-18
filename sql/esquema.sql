-- Esquema de ejemplo. Es SQL estándar: corre igual en SQLite y en SQL Server
-- (en SQL Server, DECIMAL y VARCHAR se comportan igual; la fecha se guarda como DATE).

CREATE TABLE IF NOT EXISTS clientes (
    id          INTEGER PRIMARY KEY,
    razon_social VARCHAR(120) NOT NULL,
    cuit        VARCHAR(13)  NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS facturas (
    numero       VARCHAR(13)   PRIMARY KEY,   -- formato 0001-00001234
    cliente_id   INTEGER       NOT NULL REFERENCES clientes(id),
    fecha        DATE          NOT NULL,
    vencimiento  DATE          NOT NULL,
    total        DECIMAL(14,2) NOT NULL,
    estado       VARCHAR(20)   NOT NULL DEFAULT 'pendiente',  -- pendiente | cobrada | parcial
    cobrado      DECIMAL(14,2) NOT NULL DEFAULT 0
);

-- Cobros ya registrados: evita contar dos veces el mismo movimiento si el proceso corre de nuevo
CREATE TABLE IF NOT EXISTS cobros (
    movimiento VARCHAR(64)   PRIMARY KEY,   -- huella de fecha + descripción + importe
    numero     VARCHAR(13)   NOT NULL REFERENCES facturas(numero),
    importe    DECIMAL(14,2) NOT NULL
);
