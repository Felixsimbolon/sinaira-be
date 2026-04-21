from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layanan', '0002_layanankategori_alter_layanan_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='layanan',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
