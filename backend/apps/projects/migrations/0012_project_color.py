from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0011_taskbutton_hide_when_has_label_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="color",
            field=models.CharField(
                choices=[
                    ("indigo", "Indigo"),
                    ("emerald", "Emerald"),
                    ("sky", "Sky"),
                    ("violet", "Violet"),
                    ("rose", "Rose"),
                    ("amber", "Amber"),
                    ("teal", "Teal"),
                    ("orange", "Orange"),
                    ("lime", "Lime"),
                    ("fuchsia", "Fuchsia"),
                ],
                default="indigo",
                max_length=20,
            ),
        ),
    ]
