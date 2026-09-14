from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import (
    Album,
    AlbumTrack,
    Artist,
    DistributionSubmission,
    DownloadRequest,
    PlatformLink,
    SyncRun,
    Track,
)


class PlatformLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformLink
        fields = ["id", "platform", "url", "external_id"]


def platform_links(instance) -> list[dict]:
    content_type = ContentType.objects.get_for_model(instance)
    links = PlatformLink.objects.filter(content_type=content_type, object_id=str(instance.pk))
    return PlatformLinkSerializer(links, many=True).data


class ArtistSerializer(serializers.ModelSerializer):
    platform_links = serializers.SerializerMethodField()
    portrait_url = serializers.SerializerMethodField()

    class Meta:
        model = Artist
        fields = ["id", "name", "slug", "bio", "portrait_url", "platform_links"]

    def get_platform_links(self, obj):
        return platform_links(obj)

    def get_portrait_url(self, obj):
        return obj.portrait.url if obj.portrait else ""


class TrackSerializer(serializers.ModelSerializer):
    platform_links = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    stream_url = serializers.SerializerMethodField()
    mp3_download_url = serializers.SerializerMethodField()
    wav_download_url = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = [
            "id",
            "suno_clip_id",
            "title",
            "slug",
            "description",
            "lyrics",
            "timed_lyrics",
            "cover",
            "cover_url",
            "explicit",
            "instrumental",
            "duration_seconds",
            "isrc",
            "too_lost_track_id",
            "source_image_url",
            "audio_status",
            "stream_url",
            "mp3_download_url",
            "wav_download_url",
            "platform_links",
        ]
        read_only_fields = ["suno_clip_id", "audio_status", "too_lost_track_id"]
        extra_kwargs = {"cover": {"write_only": True, "required": False}}

    def get_platform_links(self, obj):
        return platform_links(obj)

    def get_cover_url(self, obj):
        return obj.cover.url if obj.cover else obj.source_image_url

    def get_stream_url(self, obj):
        return obj.mp3_file.url if obj.mp3_file else ""

    def get_mp3_download_url(self, obj):
        return obj.mp3_file.url if obj.mp3_file else ""

    def get_wav_download_url(self, obj):
        return obj.wav_file.url if obj.wav_file else ""


class AlbumTrackSerializer(serializers.ModelSerializer):
    track = TrackSerializer()

    class Meta:
        model = AlbumTrack
        fields = ["id", "position", "track"]


class AlbumListSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    track_count = serializers.IntegerField(read_only=True)
    duration_seconds = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    platform_links = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "cover",
            "cover_url",
            "source_cover_url",
            "release_date",
            "catalog_number",
            "status",
            "public",
            "version",
            "artist",
            "track_count",
            "duration_seconds",
            "platform_links",
        ]
        extra_kwargs = {"cover": {"write_only": True, "required": False}}

    def get_cover_url(self, obj):
        return obj.cover.url if obj.cover else obj.source_cover_url

    def get_platform_links(self, obj):
        return platform_links(obj)


class AlbumDetailSerializer(AlbumListSerializer):
    album_tracks = AlbumTrackSerializer(many=True, read_only=True)
    replaces_id = serializers.UUIDField(read_only=True, allow_null=True)
    has_replacements = serializers.SerializerMethodField()
    latest_submission = serializers.SerializerMethodField()

    class Meta(AlbumListSerializer.Meta):
        fields = AlbumListSerializer.Meta.fields + [
            "suno_playlist_id",
            "upc",
            "label_name",
            "copyright_line",
            "production_line",
            "too_lost_release_id",
            "replaces_id",
            "has_replacements",
            "latest_submission",
            "album_tracks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["suno_playlist_id", "too_lost_release_id", "version", "replaces_id"]

    def get_latest_submission(self, obj):
        submission = obj.submissions.order_by("-created_at").first()
        if not submission:
            return None
        return {
            "id": submission.id,
            "kind": submission.kind,
            "status": submission.status,
            "too_lost_id": submission.too_lost_id,
            "error": submission.error,
        }

    def get_has_replacements(self, obj):
        return obj.replacements.exists()


class SyncRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncRun
        fields = "__all__"


class DownloadRequestSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source="track.title", read_only=True)

    class Meta:
        model = DownloadRequest
        fields = [
            "id",
            "track",
            "track_title",
            "formats",
            "status",
            "confirmed_at",
            "completed_at",
            "suno_period",
            "error",
            "created_at",
        ]
        read_only_fields = ["status", "confirmed_at", "completed_at", "suno_period", "error"]


class DistributionSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistributionSubmission
        fields = "__all__"
        read_only_fields = [
            "status",
            "too_lost_id",
            "payload_snapshot",
            "validation_errors",
            "response_payload",
            "submitted_at",
            "completed_at",
            "error",
        ]


class CredentialInputSerializer(serializers.Serializer):
    values = serializers.JSONField()
    display_label = serializers.CharField(required=False, allow_blank=True)


class PlatformLinkInputSerializer(serializers.ModelSerializer):
    object_type = serializers.ChoiceField(choices=["artist", "album", "track"], write_only=True)
    object_id = serializers.CharField(write_only=True)

    class Meta:
        model = PlatformLink
        fields = ["id", "platform", "url", "external_id", "object_type", "object_id"]

    def create(self, validated_data):
        model_map = {"artist": Artist, "album": Album, "track": Track}
        object_type = validated_data.pop("object_type")
        object_id = validated_data.pop("object_id")
        model = model_map[object_type]
        instance = model.objects.get(pk=object_id)
        content_type = ContentType.objects.get_for_model(instance)
        link, _ = PlatformLink.objects.update_or_create(
            platform=validated_data["platform"],
            content_type=content_type,
            object_id=str(instance.pk),
            defaults=validated_data,
        )
        return link
