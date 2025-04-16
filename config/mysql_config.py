from .read_config import config_dict

hostname = ""
port = ""
username = ""
password = ""
db_name = ""

locals().update(config_dict["mysql_config"])
sqlalchemy_database_uri = f'mysql+mysqldb://{username}:{password}@{hostname}:{port}/{db_name}?charset=utf8mb4'
