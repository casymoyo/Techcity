# Generated by Django 5.0.6 on 2024-07-23 15:01

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0030_alter_reorderlist_cost'),
    ]

    operations = [
        migrations.AddField(
            model_name='reorderlist',
            name='date',
            field=models.DateField(auto_now_add=True, default=datetime.datetime(2024, 7, 23, 15, 1, 14, 600479, tzinfo=datetime.timezone.utc)),
            preserve_default=False,
        ),
    ]