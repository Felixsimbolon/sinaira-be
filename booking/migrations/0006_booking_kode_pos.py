from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0005_alter_booking_status_bookingchangelog'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='kode_pos',
            field=models.CharField(blank=True, help_text='Postal code', max_length=10),
        ),
    ]
