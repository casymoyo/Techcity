# Generated by Django 5.0.6 on 2024-07-31 11:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_rename_contact_supplier_contact_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchaseorder',
            name='delivery_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]