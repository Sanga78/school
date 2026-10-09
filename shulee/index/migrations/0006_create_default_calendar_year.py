from datetime import date

from django.db import migrations


STANDARD_CLASS_NAMES = (
    'PP1',
    'PP2',
    'Grade 1',
    'Grade 2',
    'Grade 3',
    'Grade 4',
    'Grade 5',
    'Grade 6',
    'Grade 7',
    'Grade 8',
    'Grade 9',
)


def create_default_calendar_year(apps, schema_editor):
    AcademicYear = apps.get_model('index', 'AcademicYear')
    StudentClass = apps.get_model('index', 'StudentClass')
    database = schema_editor.connection.alias
    academic_years = AcademicYear.objects.using(database)

    if not academic_years.exists():
        academic_year = academic_years.create(
            name='2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        for class_name in STANDARD_CLASS_NAMES:
            StudentClass.objects.using(database).get_or_create(
                name=class_name,
                academic_year_id=academic_year.pk,
            )


class Migration(migrations.Migration):
    dependencies = [
        ('index', '0005_seed_standard_classes'),
    ]

    operations = [
        migrations.RunPython(create_default_calendar_year, migrations.RunPython.noop),
    ]
