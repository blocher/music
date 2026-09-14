from datetime import datetime

from django.db import migrations, models


def _source_date(payload):
    value = (payload or {}).get("created_at") or (payload or {}).get("createdAt")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def backfill_release_dates(apps, schema_editor):
    Track = apps.get_model("catalog", "Track")
    Album = apps.get_model("catalog", "Album")
    for track in Track.objects.filter(release_date__isnull=True).iterator():
        release_date = _source_date(track.source_payload)
        if release_date:
            Track.objects.filter(pk=track.pk).update(release_date=release_date)
    for album in Album.objects.filter(release_date__isnull=True).iterator():
        release_date = (
            Track.objects.filter(album_tracks__album_id=album.pk, release_date__isnull=False)
            .order_by("-release_date")
            .values_list("release_date", flat=True)
            .first()
        )
        if release_date:
            Album.objects.filter(pk=album.pk).update(release_date=release_date)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_ai_lyrics_integrations")]

    operations = [
        migrations.AddField(
            model_name="track",
            name="release_date",
            field=models.DateField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="syncrun",
            name="mode",
            field=models.CharField(
                choices=[("incremental", "New songs only"), ("full", "Refresh all Suno metadata")],
                default="incremental",
                max_length=24,
            ),
        ),
        migrations.RunPython(backfill_release_dates, migrations.RunPython.noop),
    ]
