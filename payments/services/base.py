from abc import ABC, abstractmethod


class BasePaymentService(ABC):
    """
    Abstract base class for all payment gateways.

    Callers (views) must ONLY talk to this interface via
    payments.services.factory.get_payment_service(). Swapping the live
    gateway then means writing one new subclass and flipping the
    PAYMENT_GATEWAY setting — no view/business-logic changes.
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

    # ------------------------------------------------------------------
    # CHECKOUT (generic contract — the parts that differ per gateway)
    # ------------------------------------------------------------------
    def start_checkout(self, *, payment, customer, surl, furl):
        """
        Return a gateway-neutral instruction the client (web/app) follows.

        Shapes:
          {"flow": "instant"}
              -> no external step; the view confirms + fulfils immediately.
          {"flow": "redirect_post", "action_url": "...", "params": {...}}
              -> client auto-submits an HTML form (or feeds `params` to a
                 native SDK). `params` already contains the signed hash.

        `customer` is a dict: {name, email, phone}.
        `surl` / `furl` are the absolute success/failure callback URLs.

        Default = instant (used by the fake gateway).
        """
        return {"flow": "instant"}

    def verify_callback(self, *, data):
        """
        Verify a gateway callback/webhook payload (form dict or JSON).

        Return (payment, is_valid_and_successful). Default gateways that
        have no external callback raise NotImplementedError.
        """
        raise NotImplementedError("This gateway has no callback verification.")
