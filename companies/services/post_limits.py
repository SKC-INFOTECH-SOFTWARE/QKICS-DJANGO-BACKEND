from companies.models import CompanyPost, CompanyPostSettings


def company_has_free_post(company):
    """
    Returns True if the company can still create a free post.
    """

    settings = CompanyPostSettings.objects.first()

    if not settings:
        return True  # fallback safety

    free_limit = settings.free_posts_per_company

    total_posts = CompanyPost.objects.filter(company=company, is_active=True).count()

    return total_posts < free_limit
