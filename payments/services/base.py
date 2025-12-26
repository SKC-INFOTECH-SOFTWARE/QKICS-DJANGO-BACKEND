from abc import ABC, abstractmethod


class BasePaymentService(ABC):
    """
    Abstract base class for all payment gateways.
    """

    @abstractmethod
    def create_payment(self, *, user, purpose, reference_id, amount):
        """
        Create a payment record (initiated state).
        """
        pass

    @abstractmethod
    def confirm_payment(self, *, payment):
        """
        Confirm the payment (success).
        """
        pass

    @abstractmethod
    def fail_payment(self, *, payment, reason=None):
        """
        Mark payment as failed.
        """
        pass
