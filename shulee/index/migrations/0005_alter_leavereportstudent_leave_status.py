# Generated by Django 4.2.5 on 2024-06-15 11:44

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("index", "0004_alter_attendance_attendance_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="leavereportstudent",
            name="leave_status",
            field=models.IntegerField(default=0),
        ),
    ]