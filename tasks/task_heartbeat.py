from modbus.client import modbus_client


def task_heartbeat():

    heartbeat = modbus_client.modbus_read('xq', 574, 1)[0]
    if heartbeat:
        modbus_client.modbus_write('xq', [False], 574, 1)
    else:
        modbus_client.modbus_write('xq', [True], 574, 1)
