from django.db import migrations


def forward_merge_address_into_alamat(apps, schema_editor):
    Therapist = apps.get_model('therapist', 'Therapist')

    # Preserve legacy data by copying address into alamat when alamat is empty.
    rows = Therapist.objects.exclude(address='').filter(alamat='')
    for row in rows.iterator():
        row.alamat = row.address
        row.save(update_fields=['alamat'])


def reverse_noop(apps, schema_editor):
    # No-op: removed field is not restored with historical data.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('therapist', '0012_therapist_address'),
    ]

    operations = [
        migrations.RunPython(forward_merge_address_into_alamat, reverse_noop),
        migrations.RemoveField(
            model_name='therapist',
            name='address',
        ),
    ]
