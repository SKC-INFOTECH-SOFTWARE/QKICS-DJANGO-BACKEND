from rest_framework.pagination import PageNumberPagination
from rest_framework.pagination import CursorPagination


class AdminCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"


class AdminPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminMemberCursorPagination(CursorPagination):
    page_size = 10
    ordering = "-joined_at"
