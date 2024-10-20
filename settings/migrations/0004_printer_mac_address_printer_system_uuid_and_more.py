# Generated by Django 5.0.6 on 2024-08-06 05:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0003_printer'),
    ]

    operations = [
        migrations.AddField(
            model_name='printer',
            name='mac_address',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='printer',
            name='system_uuid',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='printer',
            name='hostname',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
