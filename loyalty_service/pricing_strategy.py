from abc import ABC, abstractmethod
from loyalty_service.cached_rules_proxy import IRulesProvider


class IDiscountStrategy(ABC):
    @abstractmethod
    def calculate(self, base_price: float, total_spent: float) -> float: ...


class TierAccumulativeStrategy(IDiscountStrategy):
    def __init__(self, rules_provider: IRulesProvider):
        self._rules = rules_provider

    def calculate(self, base_price: float, total_spent: float) -> float:
        active_rules = self._rules.fetch_rules()
        rule = max(
            [r for r in active_rules if total_spent >= r["required_spend"]],
            key=lambda x: x["required_spend"]
        )
        return base_price * (rule["discount_percent"] / 100.0)


class FixedPromoStrategy(IDiscountStrategy):
    def __init__(self, percent: float):
        self._percent = percent

    def calculate(self, base_price: float, total_spent: float) -> float:
        return base_price * (self._percent / 100.0)