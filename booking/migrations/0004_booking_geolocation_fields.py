from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0003_booking_voucher_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='kecamatan',
            field=models.CharField(blank=True, help_text='Kecamatan', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='kelurahan',
            field=models.CharField(blank=True, help_text='Kelurahan', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='latitude',
            field=models.FloatField(blank=True, help_text='Latitude for booking location', null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='longitude',
            field=models.FloatField(blank=True, help_text='Longitude for booking location', null=True),
        ),
    ]
