from .read_config import config_dict

seperator = "&"
model_row = 1
prod_date_row = -1
expire_date_row = -1
shelf_life_row = -1
model_start_pos = -1
prod_date_start_pos = -1
expire_date_start_pos = -1
shelf_life_start_pos = -1
model_length = -1
prod_date_length = -1
expire_date_length = -1
shelf_life_length = -1

locals().update(config_dict["barcode_parse_config"])
