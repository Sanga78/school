# Generated by Django 4.2.5 on 2024-06-16 14:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("index", "0005_alter_leavereportstudent_leave_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffs",
            name="fcm_token",
            field=models.TextField(default=""),
        ),
        migrations.AddField(
            model_name="students",
            name="fcm_token",
            field=models.TextField(default=""),
        ),
    ]
