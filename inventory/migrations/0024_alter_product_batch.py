# Generated by Django 4.2.16 on 2024-10-19 11:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0023_alter_purchaseorder_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="batch",
            field=models.CharField(blank=True, default="", max_length=255, null=True),
        ),
    ]
