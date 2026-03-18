from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("therapist", "0009_therapist_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="therapist",
            name="alamat",
            field=models.TextField(blank=True, default="", help_text="Therapist address"),
        ),
    ]

