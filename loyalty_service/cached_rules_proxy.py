from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IRulesProvider(ABC):
    @abstractmethod
    def fetch_rules(self) -> List[Dict]:
        pass


class DatabaseRulesProvider(IRulesProvider):
    def fetch_rules(self) -> List[Dict]:
        print("  [Loyalty DB] Загрузка правил скидок из базы данных...")
        return [
            {"tier": "Basic", "required_spend": 0, "discount_percent": 0.0},
            {"tier": "Silver", "required_spend": 10000, "discount_percent": 5.0},
            {"tier": "Gold", "required_spend": 30000, "discount_percent": 10.0},
            {"tier": "Platinum", "required_spend": 60000, "discount_percent": 15.0},
        ]


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