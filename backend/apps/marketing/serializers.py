from rest_framework import serializers

from .models import CampaignAnalytics, EmailCampaign, MarketingCampaign, MarketingTask, RecurrencePattern


class CampaignAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignAnalytics
        fields = (
            "id",
            "campaign",
            "impressions",
            "clicks",
            "conversions",
            "revenue",
            "metrics",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


class EmailCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailCampaign
        fields = (
            "id",
            "campaign",
            "subject",
            "template_id",
            "list_ids",
            "open_rate",
            "click_rate",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class MarketingCampaignSerializer(serializers.ModelSerializer):
    analytics = CampaignAnalyticsSerializer(read_only=True)
    email_campaign = EmailCampaignSerializer(read_only=True)

    class Meta:
        model = MarketingCampaign
        fields = (
            "id",
            "organization",
            "name",
            "description",
            "start_date",
            "end_date",
            "status",
            "budget",
            "analytics",
            "email_campaign",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class RecurrencePatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurrencePattern
        fields = ("id", "task", "type", "interval", "weekdays", "monthdays", "end_date")
        read_only_fields = ("id",)


class MarketingTaskSerializer(serializers.ModelSerializer):
    recurrence_pattern = RecurrencePatternSerializer(read_only=True)

    class Meta:
        model = MarketingTask
        fields = (
            "id",
            "organization",
            "title",
            "description",
            "platform",
            "content",
            "hashtags",
            "media_urls",
            "status",
            "scheduled_for",
            "published_at",
            "recurring",
            "assigned_to",
            "campaign",
            "recurrence_pattern",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")
