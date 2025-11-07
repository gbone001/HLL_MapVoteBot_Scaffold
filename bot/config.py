import json

class Config:
    def __init__(self, path: str):
        self._data = None
        self._path = path
        self.reload()

    def reload(self):
        with open(self._path, "r") as f:
            self._data = json.load(f)
            self._validate()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    # TODO Implement config file validation.
    def _validate(self):
        pass