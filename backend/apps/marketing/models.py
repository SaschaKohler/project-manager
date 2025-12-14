import uuid

from django.conf import settings
from django.db import models

from apps.tenants.models import Organization


class MarketingCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELED = "CANCELED", "Canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="marketing_campaigns"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    budget = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class CampaignAnalytics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.OneToOneField(
        MarketingCampaign, on_delete=models.CASCADE, related_name="analytics"
    )
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    metrics = models.JSONField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Analytics for {self.id}"  # NOTE: was self.campaign_id


class EmailCampaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.OneToOneField(
        MarketingCampaign, on_delete=models.CASCADE, related_name="email_campaign"
    )
    subject = models.CharField(max_length=255)
    template_id = models.IntegerField(blank=True, null=True)
    list_ids = models.JSONField(default=list)
    open_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    click_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.subject


class MarketingTask(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        SCHEDULED = "SCHEDULED", "Scheduled"
        PUBLISHED = "PUBLISHED", "Published"
        CANCELED = "CANCELED", "Canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="marketing_tasks"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    platform = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    hashtags = models.JSONField(default=list, blank=True)
    media_urls = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    scheduled_for = models.DateTimeField()
    published_at = models.DateTimeField(blank=True, null=True)
    recurring = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marketing_tasks",
    )
    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.SET_NULL,
        related_name="tasks",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class RecurrencePattern(models.Model):
    class Type(models.TextChoices):
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"
        CUSTOM = "CUSTOM", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(
        MarketingTask, on_delete=models.CASCADE, related_name="recurrence_pattern"
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    interval = models.PositiveIntegerField(default=1)
    weekdays = models.JSONField(blank=True, null=True)
    monthdays = models.JSONField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.type} every {self.interval}"
