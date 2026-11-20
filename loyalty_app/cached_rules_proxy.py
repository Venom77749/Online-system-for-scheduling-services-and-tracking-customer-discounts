from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import db


class IRulesProvider(ABC):
    @abstractmethod
    def fetch_rules(self) -> List[Dict]:
        pass


class DatabaseRulesProvider(IRulesProvider):
    def fetch_rules(self) -> List[Dict]:
        print("  [Loyalty SQLite DB] Загрузка правил скидок из loyalty.db...")
        return db.fetch_discount_rules()


class CachedRulesProxy(IRulesProvider):
    def __init__(self, db_provider: DatabaseRulesProvider):
        self._db_provider = db_provider
        self._cache: Optional[List[Dict]] = None

    def fetch_rules(self) -> List[Dict]:
        if self._cache is None:
            self._cache = self._db_provider.fetch_rules()
        else:
            print("  [Loyalty Proxy] Правила взяты из in-memory кэша")
        return self._cache

    def clear(self):
        self._cache = None
