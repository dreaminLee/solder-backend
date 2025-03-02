import logging

from flask import Flask
from flask_jwt_extended import JWTManager
# from flask_socketio import SocketIO

from modbus.client import modbus_client
# from config.Logger import log_init
from router.alarm import alarm_bp
from router.auth import auth_bp
from router.solder import solder_bp
from router.solderflow import solderflow_bp
from router.sport import sport_bp
from router.station import station_bp
from router.system import system_bp
from router.temperature import temperature_bp, periodic_insertion, start_periodic_insertion
from router.user import user_bp
from router.stream import stream_bp
from tasks.scheduler import init_scheduler
# from tasks.video import video_stream

app = Flask(__name__)
# socketio = SocketIO(app)
app.config['JWT_SECRET_KEY'] = "your_secret_key"
app.config['SCHEDULER_API_ENABLED'] = True
jwt = JWTManager(app)
init_scheduler(app)
# 注册蓝图
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(stream_bp, url_prefix='/stream')
app.register_blueprint(station_bp, url_prefix='/station')
app.register_blueprint(solder_bp, url_prefix='/solder')
app.register_blueprint(alarm_bp, url_prefix='/alarm')
app.register_blueprint(temperature_bp, url_prefix='/temperature')
app.register_blueprint(solderflow_bp, url_prefix='/solderflow')
app.register_blueprint(sport_bp, url_prefix='/sport')
app.register_blueprint(system_bp, url_prefix='/system')

if __name__ == '__main__':
    logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)  # 禁用所有 SQL 语句日志
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.WARNING)  # 禁用低级日志

    # 启动温度数据插入任务
    start_periodic_insertion()
    app.run(debug=True)
