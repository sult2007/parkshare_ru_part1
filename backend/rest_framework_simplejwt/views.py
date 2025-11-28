from rest_framework.response import Response
from rest_framework.views import APIView


class TokenObtainPairView(APIView):
    def post(self, request, *args, **kwargs):
        return Response({"access": "stub", "refresh": "stub"})


class TokenRefreshView(APIView):
    def post(self, request, *args, **kwargs):
        return Response({"access": "stub"})


class TokenRefreshSlidingView(TokenRefreshView):
    pass
