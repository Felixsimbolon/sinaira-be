from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('therapist', '0003_therapist_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='therapist',
            name='kecamatan',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='therapist',
            name='kelurahan',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='therapist',
            name='kota',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='therapist',
            name='latitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='therapist',
            name='longitude',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
