from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import DistributionSubmission, DownloadRequest, PlatformLink, SyncRun, Track
from .services import save_confirmed_audio, submit_release, submit_takedown, sync_suno


@shared_task
def sync_suno_task(run_id: int):
    run = SyncRun.objects.get(pk=run_id)
    try:
        sync_suno(run)
    except Exception as exc:
        run.status = SyncRun.Status.FAILED
        run.error = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at", "updated_at"])
        raise


@shared_task
def download_audio_task(request_id: int):
    request = DownloadRequest.objects.select_related("track").get(pk=request_id)
    try:
        save_confirmed_audio(request)
    except Exception as exc:
        request.status = DownloadRequest.Status.FAILED
        request.error = str(exc)
        request.save(update_fields=["status", "error", "updated_at"])
        request.track.audio_status = Track.AudioStatus.FAILED
        request.track.save(update_fields=["audio_status", "updated_at"])
        raise


@shared_task
def submit_release_task(submission_id: int):
    submission = DistributionSubmission.objects.select_related("album", "album__artist").get(pk=submission_id)
    try:
        submit_release(submission)
    except Exception as exc:
        submission.status = DistributionSubmission.Status.FAILED
        submission.error = str(exc)
        submission.completed_at = timezone.now()
        submission.save(update_fields=["status", "error", "completed_at", "updated_at"])
        raise
    try:
        refresh_submission_task.apply_async(args=[submission.pk, 0], countdown=1800)
    except Exception:
        # A broker interruption must never relabel a successful distributor
        # submission as failed. The manual refresh action remains available.
        pass


def _album_has_store_links(submission: DistributionSubmission) -> bool:
    content_type = ContentType.objects.get_for_model(submission.album)
    return PlatformLink.objects.filter(content_type=content_type, object_id=str(submission.album_id)).exists()


@shared_task
def refresh_submission_task(submission_id: int, attempt: int = 0):
    submission = DistributionSubmission.objects.select_related("album", "album__artist").get(pk=submission_id)
    if not submission.too_lost_id or submission.status == DistributionSubmission.Status.FAILED:
        return
    if submission.status == DistributionSubmission.Status.LIVE and _album_has_store_links(submission):
        return
    try:
        from .services import refresh_submission

        refresh_submission(submission)
    except Exception:
        # Too Lost can be temporarily unavailable; the bounded polling loop is
        # deliberately resilient and the manual refresh button remains usable.
        pass
    submission.refresh_from_db(fields=["status"])
    next_attempt = attempt + 1
    finished = submission.status == DistributionSubmission.Status.FAILED or (
        submission.status == DistributionSubmission.Status.LIVE and _album_has_store_links(submission)
    )
    if not finished and next_attempt < settings.TOO_LOST_STATUS_POLL_ATTEMPTS:
        refresh_submission_task.apply_async(
            args=[submission.pk, next_attempt],
            countdown=settings.TOO_LOST_STATUS_POLL_SECONDS,
        )


@shared_task
def submit_takedown_task(submission_id: int):
    submission = DistributionSubmission.objects.select_related("album").get(pk=submission_id)
    try:
        submit_takedown(submission)
    except Exception as exc:
        submission.status = DistributionSubmission.Status.FAILED
        submission.error = str(exc)
        submission.completed_at = timezone.now()
        submission.save(update_fields=["status", "error", "completed_at", "updated_at"])
        raise
