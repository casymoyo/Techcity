# Generated by Django 5.0.6 on 2024-05-15 14:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0020_alter_stocktransaction_item"),
        ("inventory", "0010_product_tax_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stocktransaction",
            name="item",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="inventory.inventory"
            ),
        ),
    ]