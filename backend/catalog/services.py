from datetime import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .integrations.suno import SunoClient
from .integrations.too_lost import TooLostClient
from .integrations.openai import OpenAIClient
from .integrations.musixmatch import MusixmatchClient, MusixmatchPartnerAccessRequired
from .lyrics import align_transcription_to_lyrics, lyric_text_similarity, normalize_suno_alignment, timed_lyrics_payload
from .models import (
    Album,
    AlbumTrack,
    Artist,
    AuditEvent,
    DistributionSubmission,
    DownloadRequest,
    PlatformLink,
    SyncRun,
    Track,
)
from .secrets import load_credentials


def _unique_slug(model, value: str, suffix: str) -> str:
    base = slugify(value)[:200] or "untitled"
    candidate = base
    if model.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix[:8]}"
    return candidate


def _clip_from_item(item: dict) -> dict:
    return item.get("clip", item)


def _is_primary_clip(clip: dict) -> bool:
    metadata = clip.get("metadata") or {}
    clip_type = str(clip.get("type") or metadata.get("type") or "").lower()
    task = str(metadata.get("task") or "").lower()
    return clip_type not in {"stem", "persona"} and task not in {"gen_stem", "stem"}


@transaction.atomic
def sync_suno(run: SyncRun) -> SyncRun:
    run.status = SyncRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])
    client = SunoClient(load_credentials("suno"))
    artist, _ = Artist.objects.get_or_create(name="Benjamin Locher", defaults={"slug": "benjamin-locher"})
    playlist_clip_ids: set[str] = set()
    album_count = 0
    track_count = 0

    for playlist_summary in client.playlists():
        playlist_id = str(playlist_summary.get("id") or playlist_summary.get("playlist_id") or "")
        if not playlist_id:
            continue
        payload = client.playlist(playlist_id)
        title = payload.get("name") or payload.get("title") or playlist_summary.get("name") or "Untitled album"
        album = Album.objects.filter(suno_playlist_id=playlist_id).first()
        if not album:
            album = Album.objects.create(
                artist=artist,
                suno_playlist_id=playlist_id,
                title=title,
                slug=_unique_slug(Album, title, playlist_id),
                description=payload.get("description", ""),
                source_cover_url=payload.get("image_url", ""),
                source_payload=payload,
            )
        else:
            album.source_payload = payload
            album.source_cover_url = payload.get("image_url", album.source_cover_url)
            album.save(update_fields=["source_payload", "source_cover_url", "updated_at"])
        album_count += 1

        ordered_tracks = []
        for position, item in enumerate(payload.get("playlist_clips", []), start=1):
            clip = _clip_from_item(item)
            clip_id = str(clip.get("id") or "")
            if not clip_id:
                continue
            playlist_clip_ids.add(clip_id)
            metadata = clip.get("metadata") or {}
            track, created = Track.objects.get_or_create(
                suno_clip_id=clip_id,
                defaults={
                    "artist": artist,
                    "title": clip.get("title") or "Untitled track",
                    "slug": _unique_slug(Track, clip.get("title") or "Untitled track", clip_id),
                    "description": metadata.get("gpt_description_prompt") or clip.get("gpt_description_prompt") or "",
                    "lyrics": metadata.get("prompt") or clip.get("lyric") or clip.get("prompt") or "",
                    "instrumental": bool(metadata.get("make_instrumental")),
                },
            )
            track.source_audio_url = clip.get("audio_url", track.source_audio_url)
            track.source_image_url = clip.get("image_url", track.source_image_url)
            track.duration_seconds = clip.get("duration") or metadata.get("duration") or track.duration_seconds
            track.source_payload = clip
            track.save(
                update_fields=[
                    "source_audio_url",
                    "source_image_url",
                    "duration_seconds",
                    "source_payload",
                    "updated_at",
                ]
            )
            ordered_tracks.append((track, position))
            track_count += 1

        if album.status in {Album.Status.DRAFT, Album.Status.READY}:
            AlbumTrack.objects.filter(album=album).delete()
            AlbumTrack.objects.bulk_create(
                [AlbumTrack(album=album, track=track, position=position) for track, position in ordered_tracks]
            )

    all_clip_ids = {str(clip.get("id")) for clip in client.clips() if clip.get("id") and _is_primary_clip(clip)}
    run.status = SyncRun.Status.SUCCEEDED
    run.finished_at = timezone.now()
    run.albums_seen = album_count
    run.tracks_seen = track_count
    run.loose_tracks_excluded = len(all_clip_ids - playlist_clip_ids)
    run.details = {"playlist_clip_ids": len(playlist_clip_ids), "account": client.account()}
    run.save()
    return run


def suno_download_budget(now=None) -> dict:
    """Return the local, song-based monthly download allowance.

    Suno's billing response describes generation credits, not necessarily the
    scarce song-download allowance. Count distinct tracks confirmed by this app
    during the current local calendar month instead.
    """

    now = timezone.localtime(now or timezone.now())
    start = timezone.make_aware(datetime(now.year, now.month, 1), timezone.get_current_timezone())
    if now.month == 12:
        end = timezone.make_aware(datetime(now.year + 1, 1, 1), timezone.get_current_timezone())
    else:
        end = timezone.make_aware(datetime(now.year, now.month + 1, 1), timezone.get_current_timezone())

    credentials = {}
    try:
        credentials = load_credentials("suno")
    except Exception:
        pass
    try:
        limit = max(1, int(credentials.get("monthly_download_limit", 20)))
    except (TypeError, ValueError):
        limit = 20

    confirmed = DownloadRequest.objects.filter(confirmed_at__gte=start, confirmed_at__lt=end)
    used = confirmed.values("track_id").distinct().count()
    return {
        "period": start.strftime("%Y-%m"),
        "used": used,
        "limit": limit,
        "remaining": max(limit - used, 0),
        "resets_at": end.isoformat(),
    }


def validate_release(album: Album) -> list[dict]:
    errors = []
    if not album.title:
        errors.append({"field": "title", "message": "Album title is required."})
    if not album.release_date:
        errors.append({"field": "release_date", "message": "Release date is required."})
    if not album.cover:
        errors.append({"field": "cover", "message": "Final cover art is required."})
    album_tracks = list(album.album_tracks.select_related("track"))
    if not album_tracks:
        errors.append({"field": "tracks", "message": "At least one track is required."})
    for album_track in album_tracks:
        track = album_track.track
        if not track.title:
            errors.append({"field": f"track:{track.id}:title", "message": "Track title is required."})
        if not track.wav_file:
            errors.append({"field": f"track:{track.id}:wav_file", "message": "A confirmed WAV download is required."})
    return errors


def release_payload(album: Album) -> dict:
    tracks = []
    for album_track in album.album_tracks.select_related("track"):
        track = album_track.track
        item = {
            "title": track.title,
            "position": album_track.position,
            "artists": [{"name": album.artist.name, "role": "primary"}],
            "explicit": track.explicit,
            "instrumental": track.instrumental,
            "lyrics": track.lyrics,
            "audio_file_url": f"{settings.PUBLIC_BASE_URL}{track.wav_file.url}" if track.wav_file else None,
        }
        if track.isrc:
            item["isrc"] = track.isrc
        tracks.append(item)
    return {
        "title": album.title,
        "artists": [{"name": album.artist.name, "role": "primary"}],
        "release_date": album.release_date.isoformat() if album.release_date else None,
        "label": album.label_name,
        "catalog_number": album.catalog_number,
        "upc": album.upc or None,
        "copyright": album.copyright_line,
        "production_copyright": album.production_line,
        "cover_art_url": f"{settings.PUBLIC_BASE_URL}{album.cover.url}" if album.cover else None,
        "tracks": tracks,
    }


@transaction.atomic
def create_submission(album: Album, kind: str = DistributionSubmission.Kind.NEW) -> DistributionSubmission:
    errors = validate_release(album)
    return DistributionSubmission.objects.create(
        album=album,
        kind=kind,
        status=DistributionSubmission.Status.BLOCKED if errors else DistributionSubmission.Status.QUEUED,
        payload_snapshot=release_payload(album),
        validation_errors=errors,
    )


def submit_release(submission: DistributionSubmission) -> DistributionSubmission:
    if submission.validation_errors:
        return submission
    client = TooLostClient(load_credentials("too_lost"))
    result = client.create_release(submission.payload_snapshot)
    data = result.get("data", result)
    submission.too_lost_id = str(data.get("id") or data.get("release_id") or "")
    submission.response_payload = result
    submission.status = DistributionSubmission.Status.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.save()
    submission.album.too_lost_release_id = submission.too_lost_id
    submission.album.status = Album.Status.SUBMITTED
    submission.album.save(update_fields=["too_lost_release_id", "status", "updated_at"])
    apply_distribution_update(submission.album, data)
    prepare_album_lyrics_delivery(submission.album)
    return submission


def _normalize_platform(value: str) -> str:
    key = value.lower().replace(" ", "_").replace("-", "_")
    aliases = {"apple": "apple_music", "amazon": "amazon_music", "youtube": "youtube_music"}
    key = aliases.get(key, key)
    return key if key in PlatformLink.Platform.values else PlatformLink.Platform.OTHER


def _save_links(instance, links) -> None:
    content_type = ContentType.objects.get_for_model(instance)
    if isinstance(links, dict):
        normalized = []
        for platform, value in links.items():
            if isinstance(value, dict):
                normalized.append({"platform": platform, **value})
            else:
                normalized.append({"platform": platform, "url": value})
        links = normalized
    for link in links or []:
        if not isinstance(link, dict):
            continue
        url = link.get("url") or link.get("link") or link.get("href") or link.get("store_url")
        platform = link.get("platform") or link.get("store") or link.get("store_name") or link.get("dsp") or link.get("name")
        if not url or not platform:
            continue
        PlatformLink.objects.update_or_create(
            platform=_normalize_platform(str(platform)),
            content_type=content_type,
            object_id=str(instance.pk),
            defaults={
                "url": url,
                "external_id": str(
                    link.get("id") or link.get("external_id") or link.get("store_id") or link.get("platform_id") or ""
                ),
            },
        )


def _distribution_links(data: dict):
    for key in (
        "store_links",
        "storeLinks",
        "platform_links",
        "platformLinks",
        "dsp_links",
        "destinations",
        "links",
        "platforms",
    ):
        if data.get(key):
            return data[key]
    return []


@transaction.atomic
def apply_distribution_update(album: Album, payload: dict) -> Album:
    data = payload.get("data", payload)
    remote_status = str(data.get("status") or data.get("release_status") or "").lower()
    status_map = {
        "accepted": Album.Status.SUBMITTED,
        "approved": Album.Status.SUBMITTED,
        "delivered": Album.Status.SUBMITTED,
        "live": Album.Status.LIVE,
        "taken_down": Album.Status.WITHDRAWN,
        "withdrawn": Album.Status.WITHDRAWN,
    }
    if remote_status in status_map:
        album.status = status_map[remote_status]
        if album.status == Album.Status.WITHDRAWN:
            album.public = False
            album.withdrawn_at = timezone.now()
        album.save(update_fields=["status", "public", "withdrawn_at", "updated_at"])

    _save_links(album, _distribution_links(data))
    _save_links(album.artist, data.get("artist_links") or data.get("artistLinks"))
    tracks_by_isrc = {track.isrc: track for track in album.tracks.exclude(isrc="")}
    tracks_by_remote_id = {track.too_lost_track_id: track for track in album.tracks.exclude(too_lost_track_id="")}
    for remote_track in data.get("tracks", []):
        track = tracks_by_isrc.get(str(remote_track.get("isrc", ""))) or tracks_by_remote_id.get(
            str(remote_track.get("id", ""))
        )
        if not track:
            continue
        if not track.too_lost_track_id and remote_track.get("id"):
            track.too_lost_track_id = str(remote_track["id"])
            track.save(update_fields=["too_lost_track_id", "updated_at"])
        _save_links(track, _distribution_links(remote_track))
    return album


def refresh_submission(submission: DistributionSubmission) -> DistributionSubmission:
    if not submission.too_lost_id:
        return submission
    result = TooLostClient(load_credentials("too_lost")).release(submission.too_lost_id)
    submission.response_payload = result
    remote_status = str(result.get("data", result).get("status", "")).lower()
    if remote_status in {"accepted", "approved", "delivered"}:
        submission.status = DistributionSubmission.Status.ACCEPTED
    elif remote_status == "live":
        submission.status = DistributionSubmission.Status.LIVE
        submission.completed_at = timezone.now()
    elif remote_status in {"failed", "rejected"}:
        submission.status = DistributionSubmission.Status.FAILED
    submission.save(update_fields=["response_payload", "status", "completed_at", "updated_at"])
    apply_distribution_update(submission.album, result)
    prepare_album_lyrics_delivery(submission.album)
    return submission


def sync_track_lyrics(track: Track, *, force_openai: bool = False) -> Track:
    suno_error = ""
    if not force_openai:
        try:
            raw = SunoClient(load_credentials("suno")).aligned_lyrics(track.suno_clip_id)
            cues, details = normalize_suno_alignment(raw)
            details["text_similarity"] = lyric_text_similarity(cues, track.lyrics)
            details["confidence"] = min(details["confidence"], details["text_similarity"])
            if cues and details["confidence"] >= 0.72:
                track.timed_lyrics = cues
                track.lyrics_alignment_source = "suno"
                track.lyrics_alignment_status = "ready" if details["complete"] else "needs_review"
                track.lyrics_alignment_confidence = details["confidence"]
                track.lyrics_alignment_details = details
                track.lyrics_aligned_at = timezone.now()
                track.musixmatch_delivery_status = "ready"
                track.save()
                return track
            suno_error = "Suno timing was missing or below the quality threshold."
        except Exception as exc:
            suno_error = str(exc)

    audio = track.wav_file or track.mp3_file
    if not audio:
        track.lyrics_alignment_status = "needs_audio"
        track.lyrics_alignment_details = {
            "suno_error": suno_error,
            "message": "Save a confirmed MP3/WAV before using OpenAI alignment.",
        }
        track.save(update_fields=["lyrics_alignment_status", "lyrics_alignment_details", "updated_at"])
        raise ValueError("Suno timing is unavailable. Save the confirmed audio before using OpenAI alignment.")
    transcript = OpenAIClient(load_credentials("openai")).transcribe(audio, lyrics=track.lyrics)
    cues, confidence = align_transcription_to_lyrics(transcript, track.lyrics)
    if not cues:
        raise ValueError("OpenAI returned audio transcription but no usable lyric timing.")
    track.timed_lyrics = cues
    track.lyrics_alignment_source = "openai"
    track.lyrics_alignment_status = "ready" if confidence >= 0.82 else "needs_review"
    track.lyrics_alignment_confidence = confidence
    track.lyrics_alignment_details = {"confidence": confidence, "suno_error": suno_error, "line_count": len(cues)}
    track.lyrics_aligned_at = timezone.now()
    track.musixmatch_delivery_status = "ready"
    track.save()
    return track


def generate_description(*, title: str, lyrics: str, style: str, existing: str = "") -> str:
    return OpenAIClient(load_credentials("openai")).generate_description(
        title=title, lyrics=lyrics, style=style, existing=existing
    )


def generate_cover(*, title: str, prompt: str, source_image=None) -> tuple[bytes, str]:
    expanded = f"Release title: {title}. Creative direction: {prompt}"
    return OpenAIClient(load_credentials("openai")).generate_image(prompt=expanded, source_image=source_image)


def prepare_album_lyrics_delivery(album: Album) -> dict:
    """Attempt supported partner delivery and persist an honest status for every track."""
    try:
        credentials = load_credentials("musixmatch")
    except Exception:
        credentials = {}
    client = MusixmatchClient(credentials)
    summary = {"submitted": 0, "needs_partner_access": 0, "not_ready": 0, "failed": 0}
    for track in album.tracks.all():
        if track.instrumental:
            track.musixmatch_delivery_status = "not_applicable"
            track.musixmatch_last_error = ""
        elif not track.lyrics or not track.timed_lyrics:
            track.musixmatch_delivery_status = "not_ready"
            track.musixmatch_last_error = "Plain and timed lyrics are required."
            summary["not_ready"] += 1
        else:
            try:
                result = client.publish_synced_lyrics(timed_lyrics_payload(track))
                data = result.get("data", result)
                track.musixmatch_delivery_status = "submitted"
                track.musixmatch_track_id = str(data.get("track_id") or data.get("id") or "")
                track.musixmatch_last_error = ""
                track.musixmatch_submitted_at = timezone.now()
                summary["submitted"] += 1
            except MusixmatchPartnerAccessRequired as exc:
                track.musixmatch_delivery_status = "needs_partner_access"
                track.musixmatch_last_error = str(exc)
                summary["needs_partner_access"] += 1
            except Exception as exc:
                track.musixmatch_delivery_status = "failed"
                track.musixmatch_last_error = str(exc)
                summary["failed"] += 1
        track.save(
            update_fields=[
                "musixmatch_delivery_status",
                "musixmatch_track_id",
                "musixmatch_last_error",
                "musixmatch_submitted_at",
                "updated_at",
            ]
        )
    return summary


@transaction.atomic
def create_takedown_submission(album: Album) -> DistributionSubmission:
    if not album.too_lost_release_id:
        raise ValueError("This album has no Too Lost release ID.")
    if not album.replacements.filter(status=Album.Status.LIVE).exists():
        raise ValueError("A replacement must be live before the old album can be taken down.")
    submission = DistributionSubmission.objects.create(
        album=album,
        kind=DistributionSubmission.Kind.TAKEDOWN,
        status=DistributionSubmission.Status.QUEUED,
        payload_snapshot={"release_id": album.too_lost_release_id},
    )
    album.status = Album.Status.WITHDRAWING
    album.save(update_fields=["status", "updated_at"])
    return submission


def submit_takedown(submission: DistributionSubmission) -> DistributionSubmission:
    result = TooLostClient(load_credentials("too_lost")).take_down(submission.album.too_lost_release_id)
    submission.response_payload = result
    submission.status = DistributionSubmission.Status.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.save(update_fields=["response_payload", "status", "submitted_at", "updated_at"])
    return submission


@transaction.atomic
def clone_album_for_replacement(album: Album, new_track_ids: list[str], actor=None) -> Album:
    replacement = Album.objects.create(
        artist=album.artist,
        title=album.title,
        slug=_unique_slug(Album, album.title, str(album.id)),
        description=album.description,
        cover=album.cover,
        source_cover_url=album.source_cover_url,
        release_date=album.release_date,
        catalog_number=album.catalog_number,
        label_name=album.label_name,
        copyright_line=album.copyright_line,
        production_line=album.production_line,
        version=album.version + 1,
        replaces=album,
    )
    ordered = list(album.album_tracks.select_related("track"))
    tracks_by_id = {str(track.id): track for track in Track.objects.filter(id__in=new_track_ids)}
    for album_track in ordered:
        AlbumTrack.objects.create(album=replacement, track=album_track.track, position=album_track.position)
    next_position = len(ordered) + 1
    for track_id in new_track_ids:
        if track_id in tracks_by_id and not replacement.album_tracks.filter(track=tracks_by_id[track_id]).exists():
            AlbumTrack.objects.create(album=replacement, track=tracks_by_id[track_id], position=next_position)
            next_position += 1
    AuditEvent.objects.create(
        actor=actor,
        action="album.replacement_created",
        object_type="album",
        object_id=str(replacement.id),
        details={"replaces": str(album.id), "retained_track_ids": [str(item.track_id) for item in ordered]},
    )
    return replacement


def save_confirmed_audio(request: DownloadRequest) -> DownloadRequest:
    client = SunoClient(load_credentials("suno"))
    track = request.track
    request.status = DownloadRequest.Status.RUNNING
    request.save(update_fields=["status", "updated_at"])
    if "mp3" in request.formats:
        content, _ = client.download(track.source_audio_url)
        track.mp3_file.save(f"{track.suno_clip_id}.mp3", ContentFile(content), save=False)
    if "wav" in request.formats:
        content, _ = client.download(client.wav_url(track.suno_clip_id))
        track.wav_file.save(f"{track.suno_clip_id}.wav", ContentFile(content), save=False)
    track.audio_status = Track.AudioStatus.SAVED
    track.save()
    request.status = DownloadRequest.Status.SAVED
    request.completed_at = timezone.now()
    request.save(update_fields=["status", "completed_at", "updated_at"])
    return request
