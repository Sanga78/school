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


def seed_standard_classes(apps, schema_editor):
    AcademicYear = apps.get_model('index', 'AcademicYear')
    StudentClass = apps.get_model('index', 'StudentClass')
    database = schema_editor.connection.alias

    for academic_year in AcademicYear.objects.using(database).all():
        for class_name in STANDARD_CLASS_NAMES:
            StudentClass.objects.using(database).get_or_create(
                name=class_name,
                academic_year_id=academic_year.pk,
            )


class Migration(migrations.Migration):
    dependencies = [
        ('index', '0004_student_parent_email_studentapplication'),
    ]

    operations = [
        migrations.RunPython(seed_standard_classes, migrations.RunPython.noop),
    ]
