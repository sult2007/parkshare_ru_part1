from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse
from django.urls import include, path
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import routers

from accounts import views as accounts_api
from ai import views as ai_api
from parking import views as parking_views
from payments import views as payments_api
from vehicles import views as vehicles_api

router = routers.DefaultRouter()

# Accounts / пользователи (только API)
router.register(r"accounts/users", accounts_api.UserViewSet, basename="user")

# Vehicles
router.register(r"vehicles", vehicles_api.VehicleViewSet, basename="vehicle")

# Parking
router.register(r"parking/lots", parking_views.ParkingLotViewSet, basename="parking-lot")
router.register(r"parking/spots", parking_views.ParkingSpotViewSet, basename="parking-spot")
router.register(r"parking/bookings", parking_views.BookingViewSet, basename="booking")
router.register(r"parking/waitlist", parking_views.WaitlistViewSet, basename="waitlist")
router.register(r"parking/complaints", parking_views.ComplaintViewSet, basename="complaint")
router.register(
    r"parking/favorites", parking_views.FavoriteParkingSpotViewSet, basename="favorite-spot"
)
router.register(
    r"parking/saved-places", parking_views.SavedPlaceViewSet, basename="saved-place"
)

# Payments
router.register(r"payments", payments_api.PaymentViewSet, basename="payment")
router.register(
    r"payment-methods", payments_api.PaymentMethodViewSet, basename="payment-method"
)
router.register(
    r"payments/methods", payments_api.PaymentMethodViewSet, basename="payment-method-nested"
)


@never_cache
def service_worker(request):
    """
    Отдаём service-worker.js с корня домена, но физически он лежит в static/.
    """
    path = finders.find("service-worker.js")
    if not path:
        raise Http404("Service worker not found")
    with open(path, "rb") as f:
        content = f.read()
    return HttpResponse(content, content_type="application/javascript")


@never_cache
def manifest(request):
    """
    Отдаём manifest.webmanifest с правильным content-type.
    """
    path = finders.find("manifest.webmanifest")
    if not path:
        raise Http404("Manifest not found")
    with open(path, "rb") as f:
        content = f.read()
    return HttpResponse(content, content_type="application/manifest+json")


urlpatterns = [
    path("admin/", admin.site.urls),

    # PWA файлы
    path("service-worker.js", service_worker, name="service_worker"),
    path("manifest.webmanifest", manifest, name="manifest"),

    # Web‑страницы
    path("", parking_views.LandingPageView.as_view(), name="landing"),
    path("map/", parking_views.MapPageView.as_view(), name="map_page"),
    path("pwa-install/", parking_views.PWAInstallGuideView.as_view(), name="pwa_install"),
    path("личный-кабинет/", parking_views.UserDashboardView.as_view(), name="user_dashboard"),
    path("кабинет-владельца/", parking_views.OwnerDashboardView.as_view(), name="owner_dashboard"),
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),

    # Auth страницы (регистрация/логин/сброс пароля)
    path("accounts/", include("accounts.urls")),

    # API (DRF router)
    path("api/", include(router.urls)),

    # JWT auth
    path(
        "api/auth/token/",
        accounts_api.TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/auth/token/refresh/",
        accounts_api.TokenRefreshSlidingView.as_view(),
        name="token_refresh",
    ),

    # OTP / auth
    path("api/auth/request-code/", accounts_api.AuthOTPRequestView.as_view(), name="auth_request_code"),
    path("api/auth/verify-code/", accounts_api.AuthOTPVerifyView.as_view(), name="auth_verify_code"),

    # OpenAPI / документация
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path(
        "api/docs/redoc/",
        SpectacularRedocView.as_view(url_name="api-schema"),
        name="api-docs-redoc",
    ),

    # AI API (ParkMate + аналитика)
    path("api/ai/recommendations/", ai_api.RecommendationsAPIView.as_view(), name="ai_recommendations"),
    path("api/ai/stress-index/", ai_api.StressIndexAPIView.as_view(), name="ai_stress_index"),
    path("api/ai/departure-assistant/", ai_api.DepartureAssistantAPIView.as_view(), name="ai_departure_assistant"),
    path("api/ai/parkmate/config/", ai_api.ParkMateConfigAPIView.as_view(), name="parkmate_config"),
    path("api/ai/parkmate/price-forecast/", ai_api.ParkMatePriceForecastAPIView.as_view(), name="parkmate_price_forecast"),
    path("api/ai/chat/parking/", ai_api.ParkingChatAPIView.as_view(), name="ai_parking_chat"),
    path("api/ai/chat/feedback/", ai_api.ChatFeedbackAPIView.as_view(), name="ai_chat_feedback"),
    path("api/ai/llm/health/", ai_api.LLMServiceHealthAPIView.as_view(), name="ai_llm_health"),
    path("api/parking/map/", parking_views.ParkingMapAPIView.as_view(), name="parking_map"),
    path("api/geocode/", parking_views.GeocodeAPIView.as_view(), name="geocode"),

    # Payments webhooks
    path("payments/webhook/yookassa/", payments_api.YooKassaWebhookView.as_view(), name="yookassa_webhook"),
    path("payments/webhook/stripe/", payments_api.StripeWebhookView.as_view(), name="stripe_webhook"),

    # DRF browsable API login/logout
    path("api-auth/", include("rest_framework.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)