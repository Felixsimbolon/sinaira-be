# Generated manually for therapist profile fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('therapist', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='therapist',
            name='license_number',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='therapist',
            name='specialization',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='therapist',
            name='years_experience',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='therapist',
            name='consultation_rate',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='therapist',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='therapist',
            name='bio',
            field=models.TextField(blank=True, default=''),
        ),
    ]
