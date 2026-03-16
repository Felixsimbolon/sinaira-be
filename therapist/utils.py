from datetime import date, timedelta

from .models import Therapist, TherapistDateOverride, TherapistWeeklyAvailability


def _time_in_slots(target_time, slots):
    for slot in slots:
        if slot['start_time'] <= target_time < slot['end_time']:
            return True
    return False


def resolve_therapist_schedule_for_date(therapist, target_date: date) -> dict:
    overrides = TherapistDateOverride.objects.filter(
        therapist=therapist,
        date=target_date,
    ).order_by('start_time')

    if overrides.exists():
        available_overrides = overrides.filter(is_available=True)
        slots = [
            {
                'start_time': row.start_time,
                'end_time': row.end_time,
            }
            for row in available_overrides
            if row.start_time is not None and row.end_time is not None
        ]
        return {
            'date': target_date,
            'source': 'override',
            'off': len(slots) == 0,
            'slots': slots,
        }

    day_of_week = target_date.weekday()
    weekly_slots = TherapistWeeklyAvailability.objects.filter(
        therapist=therapist,
        day_of_week=day_of_week,
        is_active=True,
    ).order_by('start_time')

    slots = [
        {
            'start_time': row.start_time,
            'end_time': row.end_time,
        }
        for row in weekly_slots
    ]

    return {
        'date': target_date,
        'source': 'weekly',
        'off': len(slots) == 0,
        'slots': slots,
    }


def resolve_therapist_schedule_range(therapist, start_date: date, end_date: date) -> list[dict]:
    results = []
    current_date = start_date
    while current_date <= end_date:
        results.append(resolve_therapist_schedule_for_date(therapist, current_date))
        current_date += timedelta(days=1)
    return results


def is_therapist_user_available_for_booking(therapist_user, treatment_date, treatment_time) -> bool:
    profile = Therapist.objects.filter(username=therapist_user.username).first()
    if profile is None:
        return True

    has_timetable = (
        TherapistWeeklyAvailability.objects.filter(therapist=profile).exists()
        or TherapistDateOverride.objects.filter(therapist=profile).exists()
    )
    if not has_timetable:
        return True

    resolved = resolve_therapist_schedule_for_date(profile, treatment_date)
    if resolved['off']:
        return False

    return _time_in_slots(treatment_time, resolved['slots'])
