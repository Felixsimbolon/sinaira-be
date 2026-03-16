from django.db import models


class Therapist(models.Model):
    username = models.CharField(max_length=150, unique=True, blank=True, default="")
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    license_number = models.CharField(max_length=100, blank=True, default="")

    specialization = models.CharField(max_length=255, blank=True, default="")
    years_experience = models.PositiveIntegerField(default=0)
    consultation_rate = models.PositiveIntegerField(default=0)
    alamat = models.TextField(help_text="Therapist address")
    no_hp = models.CharField(max_length=20, blank=True, default="", db_index=True)
    kota = models.CharField(max_length=100, blank=True, null=True)
    kelurahan = models.CharField(max_length=100, blank=True, null=True)
    kecamatan = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    bio = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.license_number or 'no-license'})"


class TherapistWeeklyAvailability(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, 'Monday'
        TUESDAY = 1, 'Tuesday'
        WEDNESDAY = 2, 'Wednesday'
        THURSDAY = 3, 'Thursday'
        FRIDAY = 4, 'Friday'
        SATURDAY = 5, 'Saturday'
        SUNDAY = 6, 'Sunday'

    therapist = models.ForeignKey(
        Therapist,
        on_delete=models.CASCADE,
        related_name='weekly_availabilities',
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['therapist_id', 'day_of_week', 'start_time']
        indexes = [
            models.Index(fields=['therapist', 'day_of_week']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return (
            f'{self.therapist.name} - {self.get_day_of_week_display()} '
            f'{self.start_time}-{self.end_time}'
        )


class TherapistDateOverride(models.Model):
    class OverrideType(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        UNAVAILABLE = 'UNAVAILABLE', 'Unavailable'

    therapist = models.ForeignKey(
        Therapist,
        on_delete=models.CASCADE,
        related_name='date_overrides',
    )
    date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    override_type = models.CharField(
        max_length=20,
        choices=OverrideType.choices,
        default=OverrideType.UNAVAILABLE,
    )
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['therapist_id', 'date', 'start_time']
        indexes = [
            models.Index(fields=['therapist', 'date']),
            models.Index(fields=['therapist', 'date', 'override_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return (
            f'{self.therapist.name} - {self.date} '
            f'{self.override_type} {self.start_time}-{self.end_time}'
        )
