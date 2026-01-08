from rest_framework import serializers

from .models import Event, Project, RecurringTask, Task


class RecurringTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringTask
        fields = (
            "is_recurring",
            "recurrence_frequency",
            "recurrence_interval",
            "recurrence_end_date",
            "recurrence_max_occurrences",
            "recurrence_parent",
        )
        read_only_fields = ("recurrence_parent",)


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
    recurring = RecurringTaskSerializer(required=False)

    def validate(self, attrs):
        recurring_data = attrs.get('recurring', {})
        if recurring_data.get('is_recurring') and not recurring_data.get('recurrence_frequency'):
            raise serializers.ValidationError("recurrence_frequency is required when is_recurring is True.")
        return attrs

    def create(self, validated_data):
        recurring_data = validated_data.pop('recurring', {})
        instance = super().create(validated_data)
        if recurring_data.get('is_recurring'):
            RecurringTask.objects.create(
                task=instance,
                **recurring_data,
                recurrence_parent=instance
            )
        return instance

    def update(self, instance, validated_data):
        recurring_data = validated_data.pop('recurring', {})
        instance = super().update(instance, validated_data)
        if recurring_data:
            if hasattr(instance, 'recurring'):
                for attr, value in recurring_data.items():
                    setattr(instance.recurring, attr, value)
                instance.recurring.save()
            else:
                RecurringTask.objects.create(task=instance, **recurring_data)
        return instance

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
            "recurring",
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
