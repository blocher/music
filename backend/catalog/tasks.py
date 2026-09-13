from celery import shared_task
from django.utils import timezone

from .models import DistributionSubmission, DownloadRequest, SyncRun, Track
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
