import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Artist(TimestampedModel):
    name = models.CharField(max_length=180, unique=True, default="Benjamin Locher")
    slug = models.SlugField(max_length=180, unique=True, default="benjamin-locher")
    bio = models.TextField(blank=True)
    portrait = models.ImageField(upload_to="artists/", blank=True)
    external_ids = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class Album(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        SUBMITTED = "submitted", "Submitted"
        LIVE = "live", "Live"
        WITHDRAWING = "withdrawing", "Withdrawing"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artist = models.ForeignKey(Artist, on_delete=models.PROTECT, related_name="albums")
    suno_playlist_id = models.CharField(max_length=120, blank=True, db_index=True)
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=240, unique=True)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to="covers/", blank=True)
    source_cover_url = models.URLField(max_length=1000, blank=True)
    release_date = models.DateField(null=True, blank=True)
    catalog_number = models.CharField(max_length=80, blank=True)
    upc = models.CharField(max_length=32, blank=True)
    label_name = models.CharField(max_length=180, blank=True, default="Benjamin Locher")
    copyright_line = models.CharField(max_length=240, blank=True)
    production_line = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    public = models.BooleanField(default=False)
    source_payload = models.JSONField(default=dict, blank=True)
    too_lost_release_id = models.CharField(max_length=120, blank=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    replaces = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="replacements")
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    tracks = models.ManyToManyField("Track", through="AlbumTrack", related_name="albums")

    class Meta:
        ordering = ["-release_date", "-created_at"]

    def __str__(self):
        return self.title


class Track(TimestampedModel):
    class AudioStatus(models.TextChoices):
        REMOTE = "remote", "Remote only"
        QUEUED = "queued", "Queued"
        DOWNLOADING = "downloading", "Downloading"
        SAVED = "saved", "Saved"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artist = models.ForeignKey(Artist, on_delete=models.PROTECT, related_name="tracks")
    suno_clip_id = models.CharField(max_length=120, unique=True)
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=240)
    description = models.TextField(blank=True)
    lyrics = models.TextField(blank=True)
    timed_lyrics = models.JSONField(default=list, blank=True)
    cover = models.ImageField(upload_to="tracks/covers/", blank=True)
    explicit = models.BooleanField(default=False)
    instrumental = models.BooleanField(default=False)
    duration_seconds = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True)
    isrc = models.CharField(max_length=20, blank=True, db_index=True)
    too_lost_track_id = models.CharField(max_length=120, blank=True, db_index=True)
    source_audio_url = models.URLField(max_length=1000, blank=True)
    source_image_url = models.URLField(max_length=1000, blank=True)
    mp3_file = models.FileField(upload_to="tracks/mp3/", blank=True)
    wav_file = models.FileField(upload_to="tracks/wav/", blank=True)
    audio_status = models.CharField(max_length=24, choices=AudioStatus.choices, default=AudioStatus.REMOTE)
    source_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["artist", "slug"], name="unique_track_slug_per_artist")]

    def __str__(self):
        return self.title


class AlbumTrack(TimestampedModel):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="album_tracks")
    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name="album_tracks")
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["album", "track"], name="unique_track_per_album"),
            models.UniqueConstraint(fields=["album", "position"], name="unique_album_track_position"),
        ]


class PlatformLink(TimestampedModel):
    class Platform(models.TextChoices):
        SPOTIFY = "spotify", "Spotify"
        APPLE = "apple_music", "Apple Music"
        AMAZON = "amazon_music", "Amazon Music"
        YOUTUBE = "youtube_music", "YouTube Music"
        TIDAL = "tidal", "Tidal"
        DEEZER = "deezer", "Deezer"
        PANDORA = "pandora", "Pandora"
        SOUNDCLOUD = "soundcloud", "SoundCloud"
        OTHER = "other", "Other"

    platform = models.CharField(max_length=40, choices=Platform.choices)
    url = models.URLField(max_length=1000)
    external_id = models.CharField(max_length=240, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["platform", "content_type", "object_id"], name="unique_platform_link")
        ]


class IntegrationCredential(TimestampedModel):
    class Service(models.TextChoices):
        SUNO = "suno", "Suno"
        TOO_LOST = "too_lost", "Too Lost"

    service = models.CharField(max_length=32, choices=Service.choices, unique=True)
    encrypted_payload = models.TextField()
    display_label = models.CharField(max_length=240, blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)


class SyncRun(TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    service = models.CharField(max_length=32, default="suno")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    albums_seen = models.PositiveIntegerField(default=0)
    tracks_seen = models.PositiveIntegerField(default=0)
    loose_tracks_excluded = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)


def default_audio_formats():
    return ["mp3", "wav"]


class DownloadRequest(TimestampedModel):
    class Status(models.TextChoices):
        AWAITING_CONFIRMATION = "awaiting_confirmation", "Awaiting confirmation"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SAVED = "saved", "Saved"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="download_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    formats = models.JSONField(default=default_audio_formats)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.AWAITING_CONFIRMATION)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    suno_period = models.CharField(max_length=80, blank=True)
    error = models.TextField(blank=True)


class DistributionSubmission(TimestampedModel):
    class Kind(models.TextChoices):
        NEW = "new", "New release"
        REPLACEMENT = "replacement", "Replacement"
        TAKEDOWN = "takedown", "Takedown"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        BLOCKED = "blocked", "Blocked"
        QUEUED = "queued", "Queued"
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted"
        LIVE = "live", "Live"
        FAILED = "failed", "Failed"

    album = models.ForeignKey(Album, on_delete=models.PROTECT, related_name="submissions")
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.NEW)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    too_lost_id = models.CharField(max_length=120, blank=True, db_index=True)
    payload_snapshot = models.JSONField(default=dict)
    validation_errors = models.JSONField(default=list, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)


class AuditEvent(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=120, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
