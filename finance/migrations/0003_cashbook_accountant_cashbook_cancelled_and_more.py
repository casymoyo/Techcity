# Generated by Django 4.2.16 on 2024-09-17 11:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashbook",
            name="accountant",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AddField(
            model_name="cashbook",
            name="cancelled",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AddField(
            model_name="cashbook",
            name="director",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AddField(
            model_name="cashbook",
            name="expense",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="finance.expense",
            ),
        ),
        migrations.AddField(
            model_name="cashbook",
            name="manager",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="cashbook",
            name="sale",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="finance.sale",
            ),
        ),
    ]
