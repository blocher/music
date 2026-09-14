from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Album, AlbumTrack, Artist, AuditEvent, DistributionSubmission, PlatformLink, Track


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


class StudioAlbumDeleteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="ben", password="secret", is_staff=True)
        self.client.force_authenticate(self.user)
        self.artist, _ = Artist.objects.get_or_create(name="Benjamin Locher", defaults={"slug": "benjamin-locher"})

    def create_album(self, **overrides):
        values = {"artist": self.artist, "title": "Family Songs", "slug": "family-songs"}
        values.update(overrides)
        return Album.objects.create(**values)

    def test_deleting_draft_removes_album_data_but_preserves_track(self):
        album = self.create_album()
        track = Track.objects.create(
            artist=self.artist,
            suno_clip_id="clip-1",
            title="Kitchen Dance",
            slug="kitchen-dance",
        )
        AlbumTrack.objects.create(album=album, track=track, position=1)
        PlatformLink.objects.create(
            platform=PlatformLink.Platform.SPOTIFY,
            url="https://open.spotify.com/album/example",
            content_type=ContentType.objects.get_for_model(Album),
            object_id=str(album.pk),
        )

        response = self.client.delete(f"/api/studio/albums/{album.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Album.objects.filter(pk=album.pk).exists())
        self.assertTrue(Track.objects.filter(pk=track.pk).exists())
        self.assertFalse(AlbumTrack.objects.filter(album_id=album.pk).exists())
        self.assertFalse(PlatformLink.objects.filter(object_id=str(album.pk)).exists())
        event = AuditEvent.objects.get(action="album.deleted", object_id=str(album.pk))
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.details["tracks_preserved"], 1)

    def test_distributed_album_cannot_be_deleted(self):
        album = self.create_album(status=Album.Status.LIVE, too_lost_release_id="release-1")

        response = self.client.delete(f"/api/studio/albums/{album.pk}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Album.objects.filter(pk=album.pk).exists())

    def test_album_with_distribution_history_cannot_be_deleted(self):
        album = self.create_album()
        DistributionSubmission.objects.create(album=album)

        response = self.client.delete(f"/api/studio/albums/{album.pk}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Album.objects.filter(pk=album.pk).exists())

    def test_source_album_for_replacement_cannot_be_deleted(self):
        album = self.create_album()
        self.create_album(title="Family Songs v2", slug="family-songs-v2", replaces=album)

        response = self.client.delete(f"/api/studio/albums/{album.pk}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Album.objects.filter(pk=album.pk).exists())
