# Generated by Django 4.2.16 on 2024-10-12 02:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0016_vattransaction_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
            ],
        ),
    ]
