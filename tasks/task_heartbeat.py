from modbus.client import modbus_client

heartbeat = True

def task_heartbeat():
    if heartbeat:
        modbus_client.modbus_write('xq', [False], 574, 1)
    else:
        modbus_client.modbus_write('xq', [True], 574, 1)
