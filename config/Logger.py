import logging

# 获取 SQLAlchemy 的日志记录器
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')

# 移除所有处理器
for handler in sqlalchemy_logger.handlers[:]:
    sqlalchemy_logger.removeHandler(handler)

# 设置新的处理器（如果需要）
sqlalchemy_logger.addHandler(logging.NullHandler())  # 添加一个空处理器，完全禁用日志
