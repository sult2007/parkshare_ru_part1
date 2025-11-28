# core/pagination.py

from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class DefaultPageNumberPagination(PageNumberPagination):
    """
    Базовый пагинатор для API.
    Размер страницы берётся из настроек DRF (PAGE_SIZE), с возможностью
    переопределения через query-параметр ?page_size=.
    """

    page_size = settings.REST_FRAMEWORK.get("PAGE_SIZE", 20)
    page_size_query_param = "page_size"
    max_page_size = 100
