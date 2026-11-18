-- Facturas que todavía no se cobraron completas, con los datos del cliente.
SELECT f.numero,
       c.razon_social AS cliente,
       c.cuit,
       f.fecha,
       f.vencimiento,
       f.total,
       f.cobrado,
       f.total - f.cobrado AS saldo
FROM facturas f
JOIN clientes c ON c.id = f.cliente_id
WHERE f.estado <> 'cobrada'
ORDER BY f.vencimiento;
