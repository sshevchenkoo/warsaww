import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.db import connection
from .models import Message


def index(request):
    """Главная страница — показывает статус всех сервисов и WebSocket чат."""
    return render(request, "core/index.html")


def ping(request):
    # k8s livenessProbe: процесс жив, но не зависит от БД/Redis.
    # Если liveness бьёт в /health/ — упавший Postgres рестартит все backend-поды без пользы.
    return JsonResponse({"status": "ok"})


def healthcheck(request):
    """
    GET /health/
    Проверяет что БД и Redis живые.
    GitHub Actions и k8s readinessProbe бьют сюда.
    """
    status = {"status": "ok", "db": "ok", "redis": "ok"}
    http_status = 200

    # Проверка БД
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        status["db"] = f"error: {e}"
        status["status"] = "error"
        http_status = 500

    # Проверка Redis
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
    GET  /api/messages/  — список последних 10 сообщений из БД
    POST /api/messages/  — создать новое сообщение
    """
    if request.method == "GET":
        messages = list(
            Message.objects.order_by("-created_at")[:10].values("id", "text", "created_at")
        )
        # created_at не сериализуется в JSON напрямую
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
