# Generated by Django 5.0.6 on 2024-08-03 16:49

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationsSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_creation', models.BooleanField(default=True)),
                ('product_update', models.BooleanField(default=True)),
                ('product_deletion', models.BooleanField(default=True)),
                ('service_creation', models.BooleanField(default=True)),
                ('service_update', models.BooleanField(default=True)),
                ('service_deletion', models.BooleanField(default=True)),
                ('invoice_on_sale', models.BooleanField(default=True)),
                ('transfer_creation', models.BooleanField(default=True)),
                ('transfer_approval', models.BooleanField(default=True)),
                ('expense_creation', models.BooleanField(default=True)),
                ('expense_approval', models.BooleanField(default=True)),
                ('user_creation', models.BooleanField(default=True)),
                ('user_approval', models.BooleanField(default=True)),
                ('user_deletion', models.BooleanField(default=True)),
                ('user_login', models.BooleanField(default=True)),
            ],
        ),
    ]
