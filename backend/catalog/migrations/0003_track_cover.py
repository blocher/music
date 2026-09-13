from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_seed_artist")]
    operations = [
        migrations.AddField(
            model_name="track",
            name="cover",
            field=models.ImageField(blank=True, upload_to="tracks/covers/"),
        )
    ]
