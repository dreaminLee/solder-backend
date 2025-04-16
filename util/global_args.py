from modbus.client import modbus_client

TEMP_COLLECTION_INTERVAL = modbus_client.read_float(1502)
