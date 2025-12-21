from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate

from accounts.models import User
from ai.views import ChatStreamAPIView
from parking.models import Booking, ParkingLot, ParkingSpot


class AssistantSessionFlowTest(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="assistant_user", password="secret123")
        self.lot = ParkingLot.objects.create(
            owner=self.user,
            name="Test Lot",
            city="Москва",
            address="ул. Тестовая",
            latitude=55.75,
            longitude=37.61,
        )
        self.spot = ParkingSpot.objects.create(
            lot=self.lot,
            name="A1",
            vehicle_type=ParkingSpot.VehicleType.CAR,
            hourly_price=100,
            status=ParkingSpot.SpotStatus.ACTIVE,
        )
        start = timezone.now()
        end = start + timezone.timedelta(hours=1)
        self.booking = Booking.objects.create(
            user=self.user,
            spot=self.spot,
            start_at=start,
            end_at=end,
            status=Booking.Status.ACTIVE,
            total_price=100,
        )

    @override_settings(ENABLE_AI_CHAT=True)
    def test_structured_response_contains_sessions_and_actions(self):
        view = ChatStreamAPIView.as_view()
        request = self.factory.post(
            "/api/v1/assistant/chat/",
            {"messages": [{"role": "user", "content": "Привет"}], "structured": True},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertIn("sessions", data)
        self.assertTrue(data["sessions"])
        self.assertTrue(any(action.get("type") == "booking_extend" for action in data.get("actions", [])))

    def test_chat_disabled_returns_410(self):
        view = ChatStreamAPIView.as_view()
        request = self.factory.post(
            "/api/v1/assistant/chat/",
            {"messages": [{"role": "user", "content": "Привет"}], "structured": True},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data.get("code"), "chat_disabled")
