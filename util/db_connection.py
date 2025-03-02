from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        HOSTNAME = "127.0.0.1"
        PORT = "3306"
        USERNAME = "root"
        PASSWORD = "123456"
        DATABASE = "solder"
        DATABASE_URL = f'mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}?charset=utf8mb4'
        self.engine = create_engine(DATABASE_URL, echo=False)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

# 获取数据库实例
db_instance = Database()
