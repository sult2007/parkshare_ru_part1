from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from parking.models import ParkingLot, ParkingSpot


class PlannerApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="planner", password="secret123")

    def _create_spot(self):
        lot = ParkingLot.objects.create(
            owner=self.user,
            name="Центральная",
            city="Москва",
            address="Тверская 1",
            latitude=55.7558,
            longitude=37.6176,
        )
        ParkingSpot.objects.create(
            lot=lot,
            name="A1",
            hourly_price=100,
        )

    def test_requires_auth(self):
        resp = self.client.post(
            "/api/planner/plan/",
            {"destination_lat": 55.75, "destination_lon": 37.61},
            format="json",
        )
        self.assertIn(resp.status_code, (401, 403))

    def test_returns_recommendations_for_authenticated_user(self):
        self._create_spot()
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            "/api/planner/plan/",
            {"destination_lat": 55.75, "destination_lon": 37.61},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("recommendations", resp.data)

    def test_profile_crud(self):
        self.client.force_authenticate(self.user)
        create = self.client.post(
            "/api/planner/profiles/",
            {
                "name": "Утро",
                "destination_lat": 55.75,
                "destination_lon": 37.61,
                "requires_ev_charging": True,
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201)
        profile_id = create.data["id"]

        listing = self.client.get("/api/planner/profiles/")
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(any(p["id"] == profile_id for p in listing.data))

        patch = self.client.patch(
            f"/api/planner/profiles/{profile_id}/",
            {"name": "Утро (обновлено)"},
            format="json",
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data["name"], "Утро (обновлено)")
