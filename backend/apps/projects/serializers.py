from rest_framework import serializers

from .models import Event, Project, Task


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            "id",
            "organization",
            "title",
            "description",
            "status",
            "start_date",
            "end_date",
            "category",
            "budget",
            "priority",
            "color",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at", "organization")


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            "id",
            "project",
            "title",
            "description",
            "status",
            "priority",
            "due_date",
            "scheduled_start",
            "duration_minutes",
            "assigned_to",
            "tracked_seconds",
            "progress",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "tracked_seconds")


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = (
            "id",
            "project",
            "title",
            "description",
            "start_time",
            "end_time",
            "location",
            "type",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
