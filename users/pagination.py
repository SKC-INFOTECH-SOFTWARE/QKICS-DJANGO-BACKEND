from rest_framework.pagination import CursorPagination


class UserSearchCursorPagination(CursorPagination):
    page_size = 10
    ordering = "id"
    cursor_query_param = "cursor"
