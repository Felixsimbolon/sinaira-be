from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("therapist", "0008_merge_20260317_1637"),
    ]

    operations = [
        migrations.AddField(
            model_name="therapist",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="therapist_profile",
                to=settings.AUTH_USER_MODEL,
                help_text="Linked staff account for this therapist.",
            ),
        ),
    ]

