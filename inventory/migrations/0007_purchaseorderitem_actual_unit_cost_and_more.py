# Generated by Django 4.2.16 on 2024-09-24 16:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_alter_product_cost_alter_product_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorderitem",
            name="actual_unit_cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="product",
            name="cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
            preserve_default=False,
        ),
    ]