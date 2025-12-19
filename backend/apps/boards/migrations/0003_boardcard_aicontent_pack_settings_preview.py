from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boards", "0002_boardcard_ai_content_pack_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="boardcardaicontentpacksettings",
            name="model",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="boardcardaicontentpacksettings",
            name="preview_payload",
            field=models.TextField(blank=True, default=""),
        ),
    ]
