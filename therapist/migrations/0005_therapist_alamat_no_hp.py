from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('therapist', '0004_therapist_geolocation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='therapist',
            name='alamat',
            field=models.TextField(default='', help_text='Therapist address'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='therapist',
            name='no_hp',
            field=models.CharField(blank=True, db_index=True, default='', max_length=20),
        ),
    ]
