from django.db import migrations


def seed_artist(apps, schema_editor):
    Artist = apps.get_model("catalog", "Artist")
    Artist.objects.get_or_create(
        name="Benjamin Locher",
        defaults={"slug": "benjamin-locher"},
    )


def remove_seed_artist(apps, schema_editor):
    Artist = apps.get_model("catalog", "Artist")
    Album = apps.get_model("catalog", "Album")
    Track = apps.get_model("catalog", "Track")
    artist = Artist.objects.filter(name="Benjamin Locher", slug="benjamin-locher").first()
    if artist and not Album.objects.filter(artist=artist).exists() and not Track.objects.filter(artist=artist).exists():
        artist.delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(seed_artist, remove_seed_artist)]
