from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class adminDO(Base):
    __tablename__ = 'admin'  # 数据库表名

    admin_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_account = Column(String(50), nullable=False, unique=True)
    admin_password = Column(String(128), nullable=False)
    admin_phone = Column(String(20), nullable=True)
    admin_status = Column(Integer, nullable=False, default=1)

    def __repr__(self):
        return f"<adminDO(id={self.admin_id}, account={self.admin_account})>"
    # __tablename__ = 'admin'  # 数据库表名
    #
    # admin_id = Column(Integer, primary_key=True, autoincrement=True)
    # admin_account = Column(String(50), nullable=False, unique=True)
    # admin_password = Column(String(128), nullable=False)
    # admin_phone = Column(String(20), nullable=True)
    # admin_status = Column(Integer, nullable=False, default=1)
    #
    # def __repr__(self):
    #     return f"<adminDO(id={self.admin_id}, account={self.admin_account})>"

# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
#
# # 数据库连接 URL 示例（根据实际情况替换）
# DATABASE_URL = "mysql+pymysql://用户名:密码@localhost:3306/数据库名"
#
# # 创建数据库引擎
# engine = create_engine(DATABASE_URL, echo=True)
#
# # 创建会话工厂
# Session = sessionmaker(bind=engine)
# session = Session()
