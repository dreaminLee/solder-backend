from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from config.mysql_config import sqlalchemy_database_uri

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.engine = create_engine(sqlalchemy_database_uri, echo=False)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

# 获取数据库实例
db_instance = Database()
