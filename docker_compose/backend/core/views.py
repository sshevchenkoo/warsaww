import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.db import connection
from .models import Message


def index(request):
    """Home page — shows the status of all services and the WebSocket chat."""
    return render(request, "core/index.html")


def ping(request):
    # k8s livenessProbe: the process is alive but does not depend on the DB/Redis.
    # If liveness hits /health/ — a downed Postgres would pointlessly restart every backend pod.
    return JsonResponse({"status": "ok"})


def healthcheck(request):
    """
    GET /health/
    Checks that the DB and Redis are alive.
    GitHub Actions and the k8s readinessProbe hit this.
    """
    status = {"status": "ok", "db": "ok", "redis": "ok"}
    http_status = 200

    # Check the DB
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        status["db"] = f"error: {e}"
        status["status"] = "error"
        http_status = 500

    # Check Redis
    try:
        cache.set("healthcheck", "ok", timeout=5)
        val = cache.get("healthcheck")
        if val != "ok":
            raise Exception("cache miss")
    except Exception as e:
        status["redis"] = f"error: {e}"
        status["status"] = "error"
        http_status = 500

    return JsonResponse(status, status=http_status)


@require_http_methods(["GET", "POST"])
def messages_api(request):
    """
    GET  /api/messages/  — list the latest 10 messages from the DB
    POST /api/messages/  — create a new message
    """
    if request.method == "GET":
        messages = list(
            Message.objects.order_by("-created_at")[:10].values("id", "text", "created_at")
        )
        # created_at is not directly JSON-serializable
        for m in messages:
            m["created_at"] = m["created_at"].isoformat()
        return JsonResponse({"messages": messages})

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            text = data.get("text", "").strip()
            if not text:
                return JsonResponse({"error": "text is required"}, status=400)
            msg = Message.objects.create(text=text)
            return JsonResponse({"id": msg.id, "text": msg.text}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid json"}, status=400)
