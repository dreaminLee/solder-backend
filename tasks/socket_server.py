# tasks/socket_server.py

def start_socket_server(socketio_instance, app):
    print("Starting socket server...")
    socketio_instance.run(app, host='0.0.0.0', port=5000)
    print("Socket server started.")  # 这行代码能帮你确认服务是否启动
