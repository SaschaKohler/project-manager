import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boards", "0001_initial"),
        ("projects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BoardCardAIContentPackSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("format", models.CharField(blank=True, default="reel", max_length=32)),
                ("goal", models.CharField(blank=True, default="", max_length=255)),
                ("platform", models.CharField(blank=True, default="", max_length=64)),
                ("tone", models.CharField(blank=True, default="", max_length=64)),
                ("audience", models.CharField(blank=True, default="", max_length=255)),
                ("cta", models.CharField(blank=True, default="", max_length=255)),
                ("length", models.CharField(blank=True, default="", max_length=32)),
                ("language", models.CharField(blank=True, default="de", max_length=16)),
                ("extra_instructions", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "card",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_content_pack_settings",
                        to="boards.boardcard",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="projects.project",
                    ),
                ),
                (
                    "content_owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="board_card_ai_content_owner_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tech_owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="board_card_ai_tech_owner_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
