# Generated by Django 5.0.1 on 2024-06-05 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('index', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendance',
            name='attendance_date',
            field=models.DateField(auto_now_add=True),
        ),
    ]
