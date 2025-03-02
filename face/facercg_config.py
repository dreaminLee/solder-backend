import json
from pathlib import Path

# print(Path(__file__).parent)
rel_path = Path(__file__).parent
configs = json.load(open(rel_path / Path("config.json")))
samples_path = Path(configs["samples_path"])
samples_path.mkdir(exist_ok=True)
classifier_path = Path(configs["classifier_path"])
recognizer_path = Path(configs["recognizer_path"])
fontfile_path = Path(configs["fontfile_path"])
train_size = configs["train_size"]
