# Generated by Django 4.2.16 on 2024-10-14 08:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0014_rename_reorder_settings_reordersettings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="batch_code",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="inventory.batchcode",
            ),
        ),
    ]