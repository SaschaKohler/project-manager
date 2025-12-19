from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boards", "0003_boardcard_aicontent_pack_settings_preview"),
    ]

    operations = [
        migrations.AddField(
            model_name="boardcardaicontentpacksettings",
            name="applied_preview_payload",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="boardcardaicontentpacksettings",
            name="applied_preview_applied_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
