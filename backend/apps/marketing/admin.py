from django.contrib import admin

from .models import CampaignAnalytics, EmailCampaign, MarketingCampaign, MarketingTask, RecurrencePattern


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "name", "status", "start_date", "end_date")
    list_filter = ("status",)
    search_fields = ("name", "organization__name")


@admin.register(MarketingTask)
class MarketingTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "title", "platform", "status", "scheduled_for", "assigned_to")
    list_filter = ("status", "platform")
    search_fields = ("title", "organization__name")


@admin.register(RecurrencePattern)
class RecurrencePatternAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "type", "interval", "end_date")
    list_filter = ("type",)


@admin.register(CampaignAnalytics)
class CampaignAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "impressions", "clicks", "conversions", "revenue", "updated_at")


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "subject", "template_id", "created_at")
