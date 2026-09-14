from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import (
    Album,
    AlbumTrack,
    Artist,
    DistributionSubmission,
    DownloadRequest,
    PlatformLink,
    SyncRun,
    Track,
)
from catalog.services import (
    apply_distribution_update,
    clone_album_for_replacement,
    create_submission,
    create_takedown_submission,
    suno_download_budget,
    sync_suno,
    validate_release,
    prepare_album_lyrics_delivery,
    sync_track_lyrics,
)


class CatalogServiceTests(TestCase):
    def setUp(self):
        self.artist, _ = Artist.objects.get_or_create(name="Benjamin Locher", defaults={"slug": "benjamin-locher"})

    def track(self, title, clip_id, isrc=""):
        return Track.objects.create(
            artist=self.artist,
            title=title,
            slug=title.lower().replace(" ", "-"),
            suno_clip_id=clip_id,
            isrc=isrc,
        )

    def test_replacement_reuses_existing_tracks_and_isrcs(self):
        old = Album.objects.create(artist=self.artist, title="Night Rooms", slug="night-rooms", version=1)
        first = self.track("First", "clip-1", "USAAA2600001")
        second = self.track("Second", "clip-2", "USAAA2600002")
        new = self.track("Third", "clip-3")
        AlbumTrack.objects.create(album=old, track=first, position=1)
        AlbumTrack.objects.create(album=old, track=second, position=2)

        replacement = clone_album_for_replacement(old, [str(new.id)])

        self.assertEqual(replacement.replaces, old)
        self.assertEqual(replacement.version, 2)
        self.assertEqual(
            list(replacement.album_tracks.values_list("track_id", "position")),
            [(first.id, 1), (second.id, 2), (new.id, 3)],
        )
        self.assertEqual(replacement.album_tracks.get(track=first).track.isrc, "USAAA2600001")
        self.assertEqual(old.album_tracks.count(), 2)

    def test_release_validation_requires_final_assets(self):
        album = Album.objects.create(artist=self.artist, title="Night Rooms", slug="night-rooms")
        track = self.track("First", "clip-1")
        AlbumTrack.objects.create(album=album, track=track, position=1)

        fields = {error["field"] for error in validate_release(album)}

        self.assertEqual(fields, {"release_date", "cover", f"track:{track.id}:wav_file"})

    def test_blocked_submission_snapshots_payload_without_contacting_too_lost(self):
        album = Album.objects.create(artist=self.artist, title="Night Rooms", slug="night-rooms")

        submission = create_submission(album)

        self.assertEqual(submission.status, DistributionSubmission.Status.BLOCKED)
        self.assertEqual(submission.payload_snapshot["title"], "Night Rooms")

    def test_old_release_cannot_be_taken_down_until_replacement_is_live(self):
        old = Album.objects.create(
            artist=self.artist,
            title="Night Rooms",
            slug="night-rooms",
            status=Album.Status.LIVE,
            too_lost_release_id="release-old",
        )
        Album.objects.create(
            artist=self.artist,
            title="Night Rooms",
            slug="night-rooms-v2",
            status=Album.Status.SUBMITTED,
            replaces=old,
        )

        with self.assertRaisesMessage(ValueError, "must be live"):
            create_takedown_submission(old)

    def test_distribution_update_records_album_and_artist_store_links(self):
        album = Album.objects.create(artist=self.artist, title="Night Rooms", slug="night-rooms")

        apply_distribution_update(
            album,
            {
                "status": "live",
                "store_links": {"Spotify": "https://open.spotify.com/album/123"},
                "artist_links": [{"platform": "Apple", "url": "https://music.apple.com/artist/123"}],
            },
        )

        album.refresh_from_db()
        self.assertEqual(album.status, Album.Status.LIVE)
        self.assertEqual(PlatformLink.objects.count(), 2)

    def test_distribution_update_accepts_nested_and_camel_case_store_links(self):
        album = Album.objects.create(artist=self.artist, title="Night Rooms", slug="night-rooms")
        track = self.track("First", "clip-1", "USAAA2600001")
        AlbumTrack.objects.create(album=album, track=track, position=1)

        apply_distribution_update(
            album,
            {
                "storeLinks": {
                    "Spotify": {"href": "https://open.spotify.com/album/123", "store_id": "123"}
                },
                "tracks": [
                    {
                        "isrc": track.isrc,
                        "platformLinks": [
                            {"store_name": "Apple", "store_url": "https://music.apple.com/song/456", "platform_id": "456"}
                        ],
                    }
                ],
            },
        )

        album_link = PlatformLink.objects.get(object_id=str(album.pk))
        track_link = PlatformLink.objects.get(object_id=str(track.pk))
        self.assertEqual(album_link.external_id, "123")
        self.assertEqual(track_link.platform, PlatformLink.Platform.APPLE)

    @patch("catalog.services.load_credentials", return_value={"session_id": "session", "cookie": "cookie"})
    @patch("catalog.services.SunoClient")
    def test_sync_imports_playlist_tracks_only_and_reports_loose_songs(self, client_class, _credentials):
        client = client_class.return_value
        client.playlists.return_value = iter([{"id": "playlist-1", "name": "Night Rooms"}])
        client.playlist.return_value = {
            "id": "playlist-1",
            "name": "Night Rooms",
            "playlist_clips": [
                {
                    "clip": {
                        "id": "clip-1",
                        "title": "First",
                        "audio_url": "https://cdn.example/clip-1.mp3",
                        "metadata": {"prompt": "Line one"},
                    }
                }
            ],
        }
        client.clips.return_value = iter([{"id": "clip-1"}, {"id": "loose-clip"}])
        client.account.return_value = {"monthly_limit": 20, "monthly_usage": 3}
        run = SyncRun.objects.create()

        sync_suno(run)

        run.refresh_from_db()
        self.assertEqual(run.albums_seen, 1)
        self.assertEqual(run.tracks_seen, 1)
        self.assertEqual(run.loose_tracks_excluded, 1)
        self.assertTrue(Track.objects.filter(suno_clip_id="clip-1").exists())
        self.assertFalse(Track.objects.filter(suno_clip_id="loose-clip").exists())

    @patch("catalog.services.load_credentials", return_value={"monthly_download_limit": "20"})
    def test_download_budget_counts_confirmed_tracks_once(self, _credentials):
        first = self.track("First", "clip-1")
        second = self.track("Second", "clip-2")
        admin = get_user_model().objects.create_user(username="budget-admin")
        period = timezone.localdate().strftime("%Y-%m")
        DownloadRequest.objects.create(
            track=first,
            requested_by=admin,
            confirmed_at=timezone.now(),
            suno_period=period,
        )
        DownloadRequest.objects.create(
            track=first,
            requested_by=admin,
            confirmed_at=timezone.now(),
            suno_period=period,
        )
        DownloadRequest.objects.create(track=second, requested_by=admin)

        budget = suno_download_budget()

        self.assertEqual(budget["used"], 1)
        self.assertEqual(budget["remaining"], 19)

    @patch("catalog.services.load_credentials", return_value={"session_id": "session"})
    @patch("catalog.services.SunoClient")
    def test_suno_alignment_is_normalized_and_saved(self, client_class, _credentials):
        track = self.track("First", "clip-1")
        client_class.return_value.aligned_lyrics.return_value = {
            "hoot_cer": 0.05,
            "aligned_lyrics": [{"start_s": 2, "end_s": 4, "text": "Sing together"}],
        }

        sync_track_lyrics(track)

        track.refresh_from_db()
        self.assertEqual(track.timed_lyrics[0]["start_ms"], 2000)
        self.assertEqual(track.lyrics_alignment_source, "suno")
        self.assertEqual(track.lyrics_alignment_status, "ready")

    @patch("catalog.services.load_credentials", return_value={})
    def test_delivery_marks_partner_access_boundary(self, _credentials):
        album = Album.objects.create(artist=self.artist, title="Family", slug="family")
        track = self.track("First", "clip-1")
        track.lyrics = "Sing together"
        track.timed_lyrics = [{"start_ms": 1000, "end_ms": 2000, "text": "Sing together"}]
        track.save()
        AlbumTrack.objects.create(album=album, track=track, position=1)

        result = prepare_album_lyrics_delivery(album)

        track.refresh_from_db()
        self.assertEqual(result["needs_partner_access"], 1)
        self.assertEqual(track.musixmatch_delivery_status, "needs_partner_access")


class ReadyReleaseTests(TestCase):
    def test_valid_release_reuses_downloaded_wav(self):
        with TemporaryDirectory() as media:
            with override_settings(MEDIA_ROOT=Path(media)):
                artist, _ = Artist.objects.get_or_create(name="Benjamin Locher", defaults={"slug": "benjamin-locher"})
                album = Album.objects.create(
                    artist=artist,
                    title="Night Rooms",
                    slug="night-rooms",
                    release_date="2026-10-01",
                )
                album.cover.save("cover.jpg", ContentFile(b"cover"))
                track = Track.objects.create(
                    artist=artist,
                    title="First",
                    slug="first",
                    suno_clip_id="clip-1",
                )
                track.wav_file.save("clip-1.wav", ContentFile(b"wav"))
                AlbumTrack.objects.create(album=album, track=track, position=1)

                self.assertEqual(validate_release(album), [])
