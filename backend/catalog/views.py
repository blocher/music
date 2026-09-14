from django.contrib.auth import authenticate, login, logout
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .integrations.musixmatch import MusixmatchClient
from .integrations.openai import OpenAIClient
from .integrations.suno import SunoClient
from .integrations.too_lost import TooLostClient
from .lyrics import parse_lrc, to_lrc
from .models import (
    Album,
    Artist,
    AuditEvent,
    DistributionSubmission,
    DownloadRequest,
    IntegrationCredential,
    PlatformLink,
    SyncRun,
    Track,
)
from .permissions import IsStudioAdmin
from .secrets import load_credentials, masked_credentials, save_credentials
from .serializers import (
    AlbumDetailSerializer,
    AlbumListSerializer,
    ArtistSerializer,
    CredentialInputSerializer,
    DistributionSubmissionSerializer,
    DownloadRequestSerializer,
    PlatformLinkInputSerializer,
    SyncRunSerializer,
    TrackSerializer,
)
from .services import (
    clone_album_for_replacement,
    create_submission,
    create_takedown_submission,
    generate_cover,
    generate_description,
    prepare_album_lyrics_delivery,
    refresh_submission,
    suno_download_budget,
    sync_track_lyrics,
    validate_release,
)
from .tasks import download_audio_task, submit_release_task, submit_takedown_task, sync_suno_task


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def session_view(request):
    get_token(request)
    user = request.user
    return Response(
        {
            "authenticated": user.is_authenticated,
            "is_admin": bool(user.is_authenticated and user.is_staff),
            "name": user.get_full_name() or user.get_username() if user.is_authenticated else "",
        }
    )


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    user = authenticate(request, username=request.data.get("username"), password=request.data.get("password"))
    if not user or not user.is_staff:
        return Response({"detail": "Invalid studio credentials."}, status=status.HTTP_400_BAD_REQUEST)
    login(request, user)
    return Response(
        {
            "authenticated": True,
            "is_admin": True,
            "name": user.get_full_name() or user.get_username(),
        }
    )


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


def album_queryset(public_only=False):
    queryset = (
        Album.objects.select_related("artist")
        .annotate(
            track_count=Count("album_tracks"),
            duration_seconds=Coalesce(
                Sum("album_tracks__track__duration_seconds"),
                0,
                output_field=DecimalField(max_digits=12, decimal_places=3),
            ),
        )
        .order_by(F("release_date").desc(nulls_last=True), "-created_at")
    )
    return queryset.filter(public=True) if public_only else queryset


@api_view(["GET"])
@permission_classes([AllowAny])
def public_albums(request):
    albums = album_queryset(public_only=True)
    return Response(AlbumListSerializer(albums, many=True, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_album(request, slug):
    album = get_object_or_404(album_queryset(public_only=True).prefetch_related("album_tracks__track"), slug=slug)
    return Response(AlbumDetailSerializer(album, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_artist(request):
    artist = get_object_or_404(Artist, slug="benjamin-locher")
    return Response(ArtistSerializer(artist, context={"request": request}).data)


class AlbumViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStudioAdmin]
    lookup_field = "id"

    def get_queryset(self):
        return album_queryset().prefetch_related("album_tracks__track")

    def get_serializer_class(self):
        return AlbumListSerializer if self.action == "list" else AlbumDetailSerializer

    def destroy(self, request, *args, **kwargs):
        album_id = self.get_object().pk
        with transaction.atomic():
            album = Album.objects.select_for_update().get(pk=album_id)
            if album.status not in {Album.Status.DRAFT, Album.Status.READY} or album.too_lost_release_id:
                return Response(
                    {
                        "detail": (
                            "Only unpublished draft or ready albums can be deleted. "
                            "Take down a distributed release instead."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if album.submissions.exists():
                return Response(
                    {"detail": "This album has distribution history and cannot be deleted."},
                    status=status.HTTP_409_CONFLICT,
                )
            if album.replacements.exists():
                return Response(
                    {"detail": "This album is the source of a replacement version and cannot be deleted."},
                    status=status.HTTP_409_CONFLICT,
                )

            title = album.title
            track_count = album.album_tracks.count()
            cover_name = album.cover.name if album.cover else ""
            cover_storage = album.cover.storage if cover_name else None
            content_type = ContentType.objects.get_for_model(Album)
            PlatformLink.objects.filter(content_type=content_type, object_id=str(album.pk)).delete()
            album.delete()
            AuditEvent.objects.create(
                actor=request.user,
                action="album.deleted",
                object_type="Album",
                object_id=str(album_id),
                details={"title": title, "tracks_preserved": track_count},
            )
            if cover_name and cover_storage:
                transaction.on_commit(lambda: cover_storage.delete(cover_name))

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def validate(self, request, id=None):
        return Response({"valid": not (errors := validate_release(self.get_object())), "errors": errors})

    @action(detail=True, methods=["post"])
    def generate_description(self, request, id=None):
        album = self.get_object()
        lyrics = "\n\n".join(track.lyrics for track in album.tracks.all() if track.lyrics)
        try:
            description = generate_description(
                title=album.title,
                lyrics=lyrics,
                style=request.data.get("style", ""),
                existing=request.data.get("existing_description", album.description),
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"description": description})

    @action(detail=True, methods=["post"])
    def generate_cover(self, request, id=None):
        album = self.get_object()
        try:
            content, extension = generate_cover(
                title=album.title,
                prompt=request.data.get("prompt", "Cheerful, colorful, approachable artwork"),
                source_image=request.FILES.get("source_image"),
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)
        album.cover.save(f"ai-{album.id}.{extension}", ContentFile(content))
        return Response(self.get_serializer(album).data)

    @action(detail=True, methods=["post"])
    def deliver_lyrics(self, request, id=None):
        return Response(prepare_album_lyrics_delivery(self.get_object()))

    @action(detail=True, methods=["post"])
    def replacement(self, request, id=None):
        replacement = clone_album_for_replacement(
            self.get_object(), request.data.get("new_track_ids", []), request.user
        )
        return Response(
            AlbumDetailSerializer(replacement, context={"request": request}).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def takedown(self, request, id=None):
        try:
            submission = create_takedown_submission(self.get_object())
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=409)
        transaction.on_commit(lambda: submit_takedown_task.delay(submission.pk))
        return Response(DistributionSubmissionSerializer(submission).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def reorder(self, request, id=None):
        album = self.get_object()
        ordered_ids = [str(value) for value in request.data.get("track_ids", [])]
        existing = {str(item.track_id): item for item in album.album_tracks.all()}
        if set(ordered_ids) != set(existing):
            return Response({"detail": "Track order must contain every album track exactly once."}, status=400)
        with transaction.atomic():
            for index, track_id in enumerate(ordered_ids, start=1):
                existing[track_id].position = index + 10_000
                existing[track_id].save(update_fields=["position", "updated_at"])
            for index, track_id in enumerate(ordered_ids, start=1):
                existing[track_id].position = index
                existing[track_id].save(update_fields=["position", "updated_at"])
        return Response(AlbumDetailSerializer(album, context={"request": request}).data)


class TrackViewSet(viewsets.ModelViewSet):
    serializer_class = TrackSerializer
    permission_classes = [IsStudioAdmin]
    queryset = Track.objects.select_related("artist").order_by(F("release_date").desc(nulls_last=True), "-created_at")

    @action(detail=True, methods=["post"])
    def import_lrc(self, request, pk=None):
        track = self.get_object()
        track.timed_lyrics = parse_lrc(request.data.get("lrc", ""))
        track.lyrics_alignment_source = "manual"
        track.lyrics_alignment_status = "needs_review"
        track.musixmatch_delivery_status = "ready"
        track.save(
            update_fields=[
                "timed_lyrics",
                "lyrics_alignment_source",
                "lyrics_alignment_status",
                "musixmatch_delivery_status",
                "updated_at",
            ]
        )
        return Response(self.get_serializer(track).data)

    @action(detail=True, methods=["get"])
    def export_lrc(self, request, pk=None):
        return Response({"lrc": to_lrc(self.get_object().timed_lyrics)})

    @action(detail=True, methods=["post"])
    def sync_lyrics(self, request, pk=None):
        track = self.get_object()
        try:
            sync_track_lyrics(track, force_openai=bool(request.data.get("force_openai")))
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(self.get_serializer(track).data)

    @action(detail=True, methods=["post"])
    def generate_description(self, request, pk=None):
        track = self.get_object()
        try:
            description = generate_description(
                title=track.title,
                lyrics=request.data.get("lyrics", track.lyrics),
                style=request.data.get("style", ""),
                existing=request.data.get("existing_description", track.description),
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"description": description})

    @action(detail=True, methods=["post"])
    def generate_cover(self, request, pk=None):
        track = self.get_object()
        try:
            content, extension = generate_cover(
                title=track.title,
                prompt=request.data.get("prompt", "Cheerful, colorful, approachable artwork"),
                source_image=request.FILES.get("source_image"),
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)
        track.cover.save(f"ai-{track.id}.{extension}", ContentFile(content))
        return Response(self.get_serializer(track).data)


class DownloadRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DownloadRequestSerializer
    permission_classes = [IsStudioAdmin]
    queryset = DownloadRequest.objects.select_related("track", "requested_by").all()

    def create(self, request):
        serializer = DownloadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        track = serializer.validated_data["track"]
        if track.audio_status == Track.AudioStatus.SAVED:
            return Response({"detail": "Audio for this track is already saved."}, status=409)
        existing = (
            self.get_queryset()
            .filter(
                track=track,
                status=DownloadRequest.Status.AWAITING_CONFIRMATION,
            )
            .first()
        )
        if existing:
            return Response(DownloadRequestSerializer(existing).data)
        download = serializer.save(requested_by=request.user)
        return Response(DownloadRequestSerializer(download).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        with transaction.atomic():
            download = DownloadRequest.objects.select_for_update().select_related("track").get(pk=self.get_object().pk)
            if download.status != DownloadRequest.Status.AWAITING_CONFIRMATION:
                return Response({"detail": "This download request cannot be confirmed."}, status=409)
            budget = suno_download_budget()
            already_counted = DownloadRequest.objects.filter(
                track=download.track,
                confirmed_at__isnull=False,
                suno_period=budget["period"],
            ).exists()
            if budget["remaining"] == 0 and not already_counted:
                return Response(
                    {"detail": "The local Suno download allowance is exhausted for this month.", "budget": budget},
                    status=409,
                )
            download.status = DownloadRequest.Status.QUEUED
            download.confirmed_at = timezone.now()
            download.suno_period = budget["period"]
            download.save(update_fields=["status", "confirmed_at", "suno_period", "updated_at"])
            download.track.audio_status = Track.AudioStatus.QUEUED
            download.track.save(update_fields=["audio_status", "updated_at"])
        transaction.on_commit(lambda: download_audio_task.delay(download.pk))
        return Response({**DownloadRequestSerializer(download).data, "budget": suno_download_budget()})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        download = self.get_object()
        if download.status != DownloadRequest.Status.AWAITING_CONFIRMATION:
            return Response({"detail": "Only unconfirmed requests can be cancelled."}, status=409)
        download.status = DownloadRequest.Status.CANCELLED
        download.save(update_fields=["status", "updated_at"])
        return Response(DownloadRequestSerializer(download).data)


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DistributionSubmissionSerializer
    permission_classes = [IsStudioAdmin]
    queryset = DistributionSubmission.objects.select_related("album").all()

    def create(self, request):
        album = get_object_or_404(Album, pk=request.data.get("album"))
        submission = create_submission(album, request.data.get("kind", DistributionSubmission.Kind.NEW))
        if not submission.validation_errors:
            transaction.on_commit(lambda: submit_release_task.delay(submission.pk))
        return Response(DistributionSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        submission = refresh_submission(self.get_object())
        return Response(DistributionSubmissionSerializer(submission).data)


class PlatformLinkViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformLinkInputSerializer
    permission_classes = [IsStudioAdmin]
    queryset = PlatformLink.objects.all()


@api_view(["GET", "PUT"])
@permission_classes([IsStudioAdmin])
def integration_view(request, service):
    if service not in {"suno", "too_lost", "openai", "musixmatch"}:
        return Response({"detail": "Unknown integration."}, status=404)
    if request.method == "GET":
        return Response(masked_credentials(service))
    serializer = CredentialInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    save_credentials(service, serializer.validated_data["values"], serializer.validated_data.get("display_label", ""))
    return Response(masked_credentials(service))


@api_view(["POST"])
@permission_classes([IsStudioAdmin])
def verify_integration(request, service):
    try:
        if service == "suno":
            result = SunoClient(load_credentials(service)).account()
        elif service == "too_lost":
            result = TooLostClient(load_credentials(service)).releases()
        elif service == "openai":
            result = OpenAIClient(load_credentials(service)).verify()
        elif service == "musixmatch":
            result = MusixmatchClient(load_credentials(service)).verify()
        else:
            return Response({"detail": "Unknown integration."}, status=404)
    except Exception as exc:
        return Response({"detail": str(exc)}, status=400)
    credential = IntegrationCredential.objects.get(service=service)
    credential.last_verified_at = timezone.now()
    credential.last_error = ""
    credential.save(update_fields=["last_verified_at", "last_error", "updated_at"])
    return Response({"ok": True, "result": result})


@api_view(["GET", "POST"])
@permission_classes([IsStudioAdmin])
def sync_runs(request):
    if request.method == "GET":
        return Response(SyncRunSerializer(SyncRun.objects.order_by("-created_at", "-pk")[:20], many=True).data)
    mode = request.data.get("mode", SyncRun.Mode.INCREMENTAL)
    if mode not in SyncRun.Mode.values:
        return Response({"detail": "Sync mode must be incremental or full."}, status=400)
    run = SyncRun.objects.create(mode=mode)
    transaction.on_commit(lambda: sync_suno_task.delay(run.pk))
    return Response(SyncRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@permission_classes([IsStudioAdmin])
def download_budget(request):
    return Response(suno_download_budget())
