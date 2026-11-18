-- Deuda pendiente por cliente, de mayor a menor.
SELECT c.razon_social AS cliente,
       COUNT(*)                   AS facturas,
       SUM(f.total - f.cobrado)   AS saldo
FROM facturas f
JOIN clientes c ON c.id = f.cliente_id
WHERE f.estado <> 'cobrada'
GROUP BY c.razon_social
ORDER BY saldo DESC;
