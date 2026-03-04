from rest_framework.pagination import CursorPagination


class SlotCursorPagination(CursorPagination):

    page_size = 10
    ordering = "start_datetime"
    page_size_query_param = "page_size"
    max_page_size = 50