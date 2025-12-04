from rest_framework.pagination import CursorPagination


class PostCursorPagination(CursorPagination):
    page_size = 10
    ordering = "-created_at"
    cursor_query_param = "cursor"


class CommentCursorPagination(CursorPagination):
    page_size = 10
    ordering = "-created_at"
    cursor_query_param = "cursor"


class ReplyCursorPagination(CursorPagination):
    page_size = 10
    ordering = "created_at"
    cursor_query_param = "cursor"
