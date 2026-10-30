from abc import ABC, abstractmethod


class IMessageSender(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str) -> bool: ...


class VendorSmsSdk:
    """Сторонний провайдер SMS."""
    def send_sms_packet(self, msisdn: str, text: str) -> int:
        print(f"  [Vendor SMS SDK] Отправлено на {msisdn}: {text}")
        return 200


class SmsAdapter(IMessageSender):
    def __init__(self, sdk: VendorSmsSdk):
        self._sdk = sdk

    def send(self, recipient: str, message: str) -> bool:
        code = self._sdk.send_sms_packet(recipient, message)
        return code == 200