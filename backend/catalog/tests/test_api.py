from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Album, Artist


class PublicCatalogApiTests(TestCase):
    def setUp(self):
        self.artist, _ = Artist.objects.get_or_create(name="Benjamin Locher", defaults={"slug": "benjamin-locher"})
        Album.objects.create(artist=self.artist, title="Public", slug="public", public=True)
        Album.objects.create(artist=self.artist, title="Draft", slug="draft", public=False)

    def test_public_catalog_excludes_drafts(self):
        response = APIClient().get("/api/public/albums/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([album["title"] for album in response.json()], ["Public"])


class StudioAuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(username="ben", password="secret", is_staff=True)

    def test_session_endpoint_sets_csrf_cookie(self):
        response = self.client.get("/api/auth/session/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_non_staff_user_cannot_enter_studio(self):
        get_user_model().objects.create_user(username="listener", password="secret")
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/session/").cookies["csrftoken"].value
        response = client.post(
            "/api/auth/login/",
            {"username": "listener", "password": "secret"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 400)

    def test_staff_user_can_enter_studio_with_csrf(self):
        token = self.client.get("/api/auth/session/").cookies["csrftoken"].value

        response = self.client.post(
            "/api/auth/login/",
            {"username": "ben", "password": "secret"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_admin"])
