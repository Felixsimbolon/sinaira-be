# Add username to Therapist (for login reference / display)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('therapist', '0002_add_therapist_profile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='therapist',
            name='username',
            field=models.CharField(blank=True, default='', max_length=150, unique=True),
        ),
    ]
