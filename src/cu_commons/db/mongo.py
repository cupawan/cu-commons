"""MongoDB client (Atlas or any MongoDB)."""
import os


class Mongo:
    def __init__(self, url: str, database: str):
        if not url or not database:
            raise ValueError("Mongo URL and database name are required")
        self.url, self.database_name = url, database
        self._client = None

    @classmethod
    def from_env(cls, url_var: str = "MongoUrl", database_var: str = "MONGO_DATABASE"):
        return cls(os.environ.get(url_var, ""), os.environ.get(database_var, ""))

    @property
    def db(self):
        if self._client is None:
            import pymongo

            self._client = pymongo.MongoClient(self.url, serverSelectionTimeoutMS=15000)
        return self._client[self.database_name]

    def collection(self, name: str):
        return self.db[name]

    def insert(self, name: str, doc: dict):
        return self.collection(name).insert_one(doc).inserted_id

    def upsert(self, name: str, key: dict, doc: dict) -> None:
        self.collection(name).update_one(key, {"$set": doc}, upsert=True)

    def find(self, name: str, query: dict | None = None, limit: int = 0) -> list[dict]:
        return list(self.collection(name).find(query or {}, limit=limit))

    def find_one(self, name: str, query: dict) -> dict | None:
        return self.collection(name).find_one(query)

    def ensure_indexes(self, spec: dict[str, tuple[list, bool]]) -> list[str]:
        """spec = {collection: ([(field, 1)], unique)}"""
        return [self.collection(n).create_index(keys, unique=unique) for n, (keys, unique) in spec.items()]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
