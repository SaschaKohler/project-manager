from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0006_company_template_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="logo",
            field=models.ImageField(blank=True, null=True, upload_to="company_logos/"),
        ),
    ]
