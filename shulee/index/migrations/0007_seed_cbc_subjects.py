from django.db import migrations


STANDARD_SUBJECTS = (
    ('Language Activities', 'CBC-LANG-ACT'),
    ('Mathematical Activities', 'CBC-MATH-ACT'),
    ('Environmental Activities', 'CBC-ENV-ACT'),
    ('Psychomotor and Creative Activities', 'CBC-PSY-CRE'),
    ('Religious Activities', 'CBC-REL-ACT'),
    ('English', 'CBC-ENGLISH'),
    ('Kiswahili', 'CBC-KISWAHILI'),
    ('Indigenous Languages', 'CBC-INDIGENOUS'),
    ('Kenyan Sign Language', 'CBC-KSL'),
    ('Mathematics', 'CBC-MATH'),
    ('Science and Technology', 'CBC-SCI-TECH'),
    ('Agriculture', 'CBC-AGRICULTURE'),
    ('Social Studies', 'CBC-SOCIAL'),
    ('Creative Arts', 'CBC-CREATIVE'),
    ('Physical and Health Education', 'CBC-PHE'),
    ('Christian Religious Education', 'CBC-CRE'),
    ('Islamic Religious Education', 'CBC-IRE'),
    ('Hindu Religious Education', 'CBC-HRE'),
    ('Integrated Science', 'CBC-INTEGRATED-SCI'),
    ('Health Education', 'CBC-HEALTH'),
    ('Pre-Technical and Pre-Career Education', 'CBC-PRETECH'),
    ('Business Studies', 'CBC-BUSINESS'),
    ('Life Skills Education', 'CBC-LIFE-SKILLS'),
    ('Sports and Physical Education', 'CBC-SPORTS-PE'),
    ('Visual Arts', 'CBC-VISUAL-ARTS'),
    ('Performing Arts', 'CBC-PERFORMING-ARTS'),
    ('Computer Science', 'CBC-COMPUTER-SCI'),
    ('French', 'CBC-FRENCH'),
    ('German', 'CBC-GERMAN'),
    ('Mandarin', 'CBC-MANDARIN'),
    ('Arabic', 'CBC-ARABIC'),
)


def seed_cbc_subjects(apps, schema_editor):
    Subject = apps.get_model('index', 'Subject')
    database = schema_editor.connection.alias
    subjects = Subject.objects.using(database)

    for name, code in STANDARD_SUBJECTS:
        if subjects.filter(name__iexact=name).exists():
            continue
        subjects.get_or_create(code=code, defaults={'name': name})


class Migration(migrations.Migration):
    dependencies = [
        ('index', '0006_create_default_calendar_year'),
    ]

    operations = [
        migrations.RunPython(seed_cbc_subjects, migrations.RunPython.noop),
    ]
