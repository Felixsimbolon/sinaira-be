# Add address (alamat) to Therapist

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('therapist', '0003_therapist_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='therapist',
            name='address',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
