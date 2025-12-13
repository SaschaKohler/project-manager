from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_alter_task_options_task_sort_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="scheduled_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="task",
            name="duration_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
