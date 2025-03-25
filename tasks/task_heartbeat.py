from modbus.client import modbus_client

def task_heartbeat():
    heart_beat = modbus_client.modbus_read('xq', 574, 1)
    if heart_beat == [True]:
        modbus_client.modbus_write('xq', [False], 574, 1)
    else:
        modbus_client.modbus_write('xq', [True], 574, 1)
