# Generated by Django 4.2.16 on 2024-09-27 16:28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0011_alter_product_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorderitem",
            name="expected_profit",
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
    ]
