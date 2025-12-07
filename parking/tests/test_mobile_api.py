from rest_framework.test import APITestCase

from accounts.models import User
from parking.models import ParkingLot, ParkingSpot


class MobileAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mobile_user", password="secret123")
        lot = ParkingLot.objects.create(
            owner=self.user,
            name="Mobile Lot",
            city="Москва",
            address="Проверочная 1",
            latitude=55.75,
            longitude=37.61,
        )
        ParkingSpot.objects.create(
            lot=lot,
            name="M1",
            vehicle_type=ParkingSpot.VehicleType.CAR,
            hourly_price=150,
            status=ParkingSpot.SpotStatus.ACTIVE,
        )

    def test_search_geojson_cached_for_anonymous(self):
        url = "/api/v1/search/?format=geojson&city=Москва"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("features", response.data)
        cached = self.client.get(url)
        self.assertEqual(cached.data, response.data)
