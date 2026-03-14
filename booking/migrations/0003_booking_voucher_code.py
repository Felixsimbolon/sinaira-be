from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0002_booking_booking_id_booking_notes_booking_therapist_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='voucher_code',
            field=models.CharField(blank=True, help_text='Applied voucher code for this booking', max_length=100),
        ),
    ]
