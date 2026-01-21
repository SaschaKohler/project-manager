from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0005_invoice_number_unique_per_company"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="default_pdf_template",
            field=models.CharField(
                choices=[
                    ("classic", "Classic"),
                    ("modern", "Modern"),
                    ("elegant", "Elegant"),
                    ("minimal", "Minimal"),
                ],
                default="classic",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="theme_color_primary",
            field=models.CharField(default="#7e56c2", max_length=7),
        ),
        migrations.AddField(
            model_name="company",
            name="theme_color_secondary",
            field=models.CharField(default="#6b9080", max_length=7),
        ),
        migrations.AddField(
            model_name="company",
            name="theme_color_accent",
            field=models.CharField(default="#c9a227", max_length=7),
        ),
    ]
