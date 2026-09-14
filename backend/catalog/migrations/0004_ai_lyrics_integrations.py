from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_track_cover")]

    operations = [
        migrations.AlterField(
            model_name="integrationcredential",
            name="service",
            field=models.CharField(
                choices=[
                    ("suno", "Suno"),
                    ("too_lost", "Too Lost"),
                    ("openai", "OpenAI"),
                    ("musixmatch", "Musixmatch"),
                ],
                max_length=32,
                unique=True,
            ),
        ),
        migrations.AddField(model_name="track", name="lyrics_alignment_source", field=models.CharField(blank=True, max_length=24)),
        migrations.AddField(model_name="track", name="lyrics_alignment_status", field=models.CharField(default="not_started", max_length=32)),
        migrations.AddField(model_name="track", name="lyrics_alignment_confidence", field=models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
        migrations.AddField(model_name="track", name="lyrics_alignment_details", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="track", name="lyrics_aligned_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="track", name="musixmatch_delivery_status", field=models.CharField(default="not_ready", max_length=32)),
        migrations.AddField(model_name="track", name="musixmatch_track_id", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="track", name="musixmatch_last_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="track", name="musixmatch_submitted_at", field=models.DateTimeField(blank=True, null=True)),
    ]
