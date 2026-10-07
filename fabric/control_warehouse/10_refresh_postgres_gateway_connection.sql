-- Repoint the control-plane connection identity after the host's LAN address changed.
-- Credentials remain in the Fabric gateway connection; this only updates the stable ID.
UPDATE control.ctl_connection
SET fabric_connection_id = 'e3607aae-ab0a-4954-968c-613ebd192eeb',
    connection_name = 'conn_postgresql_salefisher_gateway',
    connection_type = 'on_premises_gateway',
    gateway_name = 'gw_local_postgres',
    is_active = CAST(1 AS BIT)
WHERE connection_id = 101;

SELECT connection_id, connection_name, connection_type, gateway_name, fabric_connection_id, is_active
FROM control.ctl_connection
WHERE connection_id = 101;
