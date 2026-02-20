from rest_framework.pagination import CursorPagination


class ExpertCursorPagination(CursorPagination):
    page_size = 10
    ordering = "-created_at"
    cursor_query_param = "cursor"