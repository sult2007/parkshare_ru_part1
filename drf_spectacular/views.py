from rest_framework.response import Response
from rest_framework.views import APIView


class SpectacularAPIView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({"schema": "stub"})


class SpectacularSwaggerView(APIView):
    url_name = None

    def get(self, request, *args, **kwargs):
        return Response({"swagger": "stub"})


class SpectacularRedocView(APIView):
    url_name = None

    def get(self, request, *args, **kwargs):
        return Response({"redoc": "stub"})

__all__ = [
    "SpectacularAPIView",
    "SpectacularSwaggerView",
    "SpectacularRedocView",
]
