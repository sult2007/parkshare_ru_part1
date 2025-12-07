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
from core.metrics import metrics_view
from parking import views as parking_views
from payments import views as payments_api
from vehicles import views as vehicles_api

from ..health import healthz, readyz

ENABLE_LABS = getattr(settings, "ENABLE_LAB_ENDPOINTS", False)
router = routers.DefaultRouter()

router.register(r"accounts/users", accounts_api.UserViewSet, basename="user")
router.register(r"vehicles", vehicles_api.VehicleViewSet, basename="vehicle")
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
router.register(
    r"parking/push-subscriptions",
    parking_views.PushSubscriptionViewSet,
    basename="push-subscription",
)
router.register(r"payments", payments_api.PaymentViewSet, basename="payment")
router.register(
    r"payment-methods", payments_api.PaymentMethodViewSet, basename="payment-method"
)
router.register(
    r"payments/methods", payments_api.PaymentMethodViewSet, basename="payment-method-nested"
)

api_v1_patterns = [
    path("", include(router.urls)),
    path("search/", parking_views.ParkingSearchAPIView.as_view(), name="v1_search"),
    path("details/<uuid:spot_id>/", parking_views.ParkingDetailsAPIView.as_view(), name="v1_details"),
    path("booking/start/", parking_views.BookingStartAPIView.as_view(), name="v1_booking_start"),
    path("booking/extend/", parking_views.BookingExtendAPIView.as_view(), name="v1_booking_extend"),
    path("booking/stop/", parking_views.BookingStopAPIView.as_view(), name="v1_booking_stop"),
    path("booking/active/", parking_views.ActiveBookingAPIView.as_view(), name="v1_booking_active"),
    path("assistant/chat/", ai_api.ChatStreamAPIView.as_view(), name="v1_assistant_chat"),
    path("auth/token/", accounts_api.TokenObtainPairView.as_view(), name="v1_token_obtain_pair"),
    path("auth/token/refresh/", accounts_api.TokenRefreshSlidingView.as_view(), name="v1_token_refresh"),
    path("auth/register/", accounts_api.UserViewSet.as_view({"post": "register"}), name="v1_auth_register"),
    path("auth/login/", accounts_api.UserViewSet.as_view({"post": "login"}), name="v1_auth_login"),
    path("auth/logout/", accounts_api.UserViewSet.as_view({"post": "logout"}), name="v1_auth_logout"),
    path("auth/mfa/verify/", accounts_api.AuthMFAVerifyView.as_view(), name="v1_auth_mfa_verify"),
    path("auth/mfa/setup/", accounts_api.AuthMFASetupView.as_view(), name="v1_auth_mfa_setup"),
    path("auth/mfa/activate/", accounts_api.AuthMFAActivateView.as_view(), name="v1_auth_mfa_activate"),
    path("auth/mfa/disable/", accounts_api.AuthMFADisableView.as_view(), name="v1_auth_mfa_disable"),
    path("auth/otp/request/", accounts_api.AuthOTPRequestView.as_view(), name="v1_auth_otp_request"),
    path("auth/otp/verify/", accounts_api.AuthOTPVerifyView.as_view(), name="v1_auth_otp_verify"),
    path("ai/chat/", ai_api.ChatStreamAPIView.as_view(), name="v1_ai_chat_stream"),
    path("ai/parkmate/config/", ai_api.ParkMateConfigAPIView.as_view(), name="v1_parkmate_config"),
    path("parking/map/", parking_views.ParkingMapAPIView.as_view(), name="v1_parking_map"),
    path("geocode/", parking_views.GeocodeAPIView.as_view(), name="v1_geocode"),
]


@never_cache
def service_worker(request):
    path = finders.find("service-worker.js")
    if not path:
        raise Http404("Service worker not found")
    with open(path, "rb") as f:
        content = f.read()
    return HttpResponse(content, content_type="application/javascript")


@never_cache
def manifest(request):
    path = finders.find("manifest.webmanifest")
    if not path:
        raise Http404("Manifest not found")
    with open(path, "rb") as f:
        content = f.read()
    return HttpResponse(content, content_type="application/manifest+json")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("metrics", metrics_view, name="metrics"),

    path("service-worker.js", service_worker, name="service_worker"),
    path("manifest.webmanifest", manifest, name="manifest"),

    path("", parking_views.LandingPageView.as_view(), name="landing"),
    path("map/", parking_views.MapPageView.as_view(), name="map_page"),
    path("pwa-install/", parking_views.PWAInstallGuideView.as_view(), name="pwa_install"),
    path("личный-кабинет/", parking_views.UserDashboardView.as_view(), name="user_dashboard"),
    path("кабинет-владельца/", parking_views.OwnerDashboardView.as_view(), name="owner_dashboard"),
    path("booking/confirm/", parking_views.BookingConfirmView.as_view(), name="booking_confirm"),
    path("payments/methods/", parking_views.PaymentMethodsPageView.as_view(), name="payment_methods"),
    path("profile/settings/", parking_views.ProfileSettingsView.as_view(), name="profile_settings"),
    path("promos/activate/", parking_views.PromoActivateView.as_view(), name="promo_activate"),
    path("business/reports/", parking_views.BusinessReportsView.as_view(), name="business_reports"),
    path("admin/metrics-lite/", parking_views.MetricsDashboardView.as_view(), name="metrics_dashboard"),
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),
    path("assistant/", TemplateView.as_view(template_name="ai/concierge.html"), name="ai_chat"),
    path("ai/", TemplateView.as_view(template_name="ai/concierge.html")),

    path("accounts/", include("accounts.urls")),

    path("auth/otp/request/", accounts_api.AuthOTPRequestView.as_view(), name="auth_otp_request"),
    path("auth/otp/verify/", accounts_api.AuthOTPVerifyView.as_view(), name="auth_otp_verify"),
    path("auth/mfa/verify/", accounts_api.AuthMFAVerifyView.as_view(), name="auth_mfa_verify"),
    path("auth/mfa/setup/", accounts_api.AuthMFASetupView.as_view(), name="auth_mfa_setup_api"),
    path("auth/mfa/activate/", accounts_api.AuthMFAActivateView.as_view(), name="auth_mfa_activate_api"),
    path("auth/mfa/disable/", accounts_api.AuthMFADisableView.as_view(), name="auth_mfa_disable_api"),
    path("auth/oauth/<str:provider>/start/", accounts_api.SocialOAuthStartView.as_view(), name="oauth_start"),
    path("auth/oauth/<str:provider>/callback/", accounts_api.SocialOAuthCallbackView.as_view(), name="oauth_callback"),

    path("api/", include(router.urls)),
    path("api/v1/", include((api_v1_patterns, "api_v1"), namespace="api_v1")),

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
    path("api/auth/mfa/verify/", accounts_api.AuthMFAVerifyView.as_view(), name="api_auth_mfa_verify"),
    path("api/auth/mfa/setup/", accounts_api.AuthMFASetupView.as_view(), name="api_auth_mfa_setup"),
    path("api/auth/mfa/activate/", accounts_api.AuthMFAActivateView.as_view(), name="api_auth_mfa_activate"),
    path("api/auth/mfa/disable/", accounts_api.AuthMFADisableView.as_view(), name="api_auth_mfa_disable"),

    path("api/auth/request-code/", accounts_api.AuthOTPRequestView.as_view(), name="auth_request_code"),
    path("api/auth/verify-code/", accounts_api.AuthOTPVerifyView.as_view(), name="auth_verify_code"),
    path("api/accounts/social-accounts/<int:pk>/", accounts_api.SocialAccountDetailView.as_view(), name="social_account_unlink"),

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

    path("api/parking/map/", parking_views.ParkingMapAPIView.as_view(), name="parking_map"),
    path("api/geocode/", parking_views.GeocodeAPIView.as_view(), name="geocode"),

    path("payments/webhook/yookassa/", payments_api.YooKassaWebhookView.as_view(), name="yookassa_webhook"),
    path("payments/webhook/stripe/", payments_api.StripeWebhookView.as_view(), name="stripe_webhook"),

    path("api-auth/", include("rest_framework.urls")),
]

if ENABLE_LABS:
    urlpatterns += [
        path("api/ai/recommendations/", ai_api.RecommendationsAPIView.as_view(), name="ai_recommendations"),
        path("api/ai/stress-index/", ai_api.StressIndexAPIView.as_view(), name="ai_stress_index"),
        path("api/ai/departure-assistant/", ai_api.DepartureAssistantAPIView.as_view(), name="ai_departure_assistant"),
        path("api/ai/parkmate/config/", ai_api.ParkMateConfigAPIView.as_view(), name="parkmate_config"),
        path("api/ai/parkmate/price-forecast/", ai_api.ParkMatePriceForecastAPIView.as_view(), name="parkmate_price_forecast"),
        path("api/chat/", ai_api.ChatStreamAPIView.as_view(), name="ai_chat_stream"),
        path("api/ai/llm/health/", ai_api.LLMServiceHealthAPIView.as_view(), name="ai_llm_health"),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
