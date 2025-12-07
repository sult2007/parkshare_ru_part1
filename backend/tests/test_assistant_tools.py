from django.test import TestCase
from accounts.models import User
from parking.models import ParkingLot, ParkingSpot, FavoriteParkingSpot
from ai import tools
from ai.tools import ToolError
from django.utils import timezone


class AssistantToolsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tool", password="pass")
        lot = ParkingLot.objects.create(
            owner=self.user,
            name="Lot",
            city="Москва",
            address="Адрес",
            latitude=55.75,
            longitude=37.61,
            is_active=True,
            is_approved=True,
        )
        self.spot = ParkingSpot.objects.create(
            lot=lot,
            name="S1",
            vehicle_type=ParkingSpot.VehicleType.CAR,
            hourly_price=100,
            status=ParkingSpot.SpotStatus.ACTIVE,
        )

    def test_search_parking(self):
        results = tools.search_parking({"city": "Москва"}, self.user)
        self.assertTrue(any(r["id"] == str(self.spot.id) for r in results))

    def test_toggle_favorite(self):
        res = tools.toggle_favorite(self.user, str(self.spot.id))
        self.assertTrue(res["favorite"])
        res2 = tools.toggle_favorite(self.user, str(self.spot.id))
        self.assertFalse(res2["favorite"])

    def test_booking_requires_auth(self):
        with self.assertRaises(ToolError):
            tools.create_booking(None, str(self.spot.id), {"hours": 1})
