from rest_framework.pagination import CursorPagination


class NotificationCursorPagination(CursorPagination):
    """
    Cursor pagination for notifications.
    Consistent with the rest of the app (bookings, community, etc.)
    Most recent notifications come first.
    """

    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"
    max_page_size = 100
