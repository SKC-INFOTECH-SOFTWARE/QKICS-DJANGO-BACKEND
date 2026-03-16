from payments.services.fake import FakePaymentService
from payments.models import Payment


def process_company_post_payment(*, user, company, amount):
    """
    Creates and confirms payment for a company post.
    """

    payment_service = FakePaymentService()

    payment = payment_service.create_payment(
        user=user,
        purpose=Payment.PURPOSE_COMPANY_POST,
        reference_id=company.id,
        amount=amount,
    )

    payment = payment_service.confirm_payment(payment=payment)

    return payment
