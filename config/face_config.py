from .read_config import config_dict
from pathlib import Path

samples_path = ""
classifier_path = ""
recognizer_path = ""
fontfile_path = ""
train_size = 30

locals().update(config_dict["face_config"])

samples_path = Path(samples_path)
classifier_path = Path(classifier_path)
recognizer_path = Path(recognizer_path)
fontfile_path = Path(fontfile_path)
# train_size = int(train_size)
