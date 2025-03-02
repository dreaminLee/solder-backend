# 配置文件
# mysql主机名
HOSTNAME = "127.0.0.1"
# mysql端口号
PORT = "3306"
USERNAME = "root"
PASSWORD = "123456"
DATABASE = "solder"
SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}?charset=utf8mb4'
