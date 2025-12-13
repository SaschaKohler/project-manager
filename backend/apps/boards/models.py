import uuid

from django.conf import settings
from django.db import models

from apps.tenants.models import Organization


class Board(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="boards")
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_boards")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class BoardColumn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="columns")
    title = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self) -> str:
        return f"{self.board.title}: {self.title}"


class BoardCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    column = models.ForeignKey(BoardColumn, on_delete=models.CASCADE, related_name="cards")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_board_cards")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self) -> str:
        return self.title


class BoardCardLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(BoardCard, on_delete=models.CASCADE, related_name="links")
    title = models.CharField(max_length=255, blank=True, default="")
    url = models.URLField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.url


def _board_attachment_upload_to(instance: "BoardCardAttachment", filename: str) -> str:
    return f"boards/{instance.card_id}/{filename}"


class BoardCardAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(BoardCard, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=_board_attachment_upload_to)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="board_attachments")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.file.name
