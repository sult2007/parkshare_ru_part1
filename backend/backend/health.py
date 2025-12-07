from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    try:
        conn = connections["default"]
        conn.cursor()
        return JsonResponse({"status": "ready"})
    except OperationalError:
        return JsonResponse({"status": "db_unavailable"}, status=503)
