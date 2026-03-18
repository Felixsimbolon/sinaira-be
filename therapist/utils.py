from datetime import date, time, timedelta

from .models import Therapist, TherapistDateOverride, TherapistWeeklyAvailability


GRID_START_TIME = time(7, 0)
GRID_END_TIME = time(20, 0)
DEFAULT_AVAILABLE_START_TIME = time(9, 0)
DEFAULT_AVAILABLE_END_TIME = time(19, 0)


def _merge_intervals(intervals):
    if not intervals:
        return []

    sorted_intervals = sorted(intervals, key=lambda x: x['start_time'])
    merged = [sorted_intervals[0]]

    for current in sorted_intervals[1:]:
        last = merged[-1]
        if current['start_time'] <= last['end_time']:
            last['end_time'] = max(last['end_time'], current['end_time'])
        else:
            merged.append(current)

    return merged


def _subtract_interval(base_intervals, cut_start, cut_end):
    result = []
    for interval in base_intervals:
        start_time = interval['start_time']
        end_time = interval['end_time']

        if cut_end <= start_time or cut_start >= end_time:
            result.append(interval)
            continue

        if cut_start > start_time:
            result.append({'start_time': start_time, 'end_time': cut_start})
        if cut_end < end_time:
            result.append({'start_time': cut_end, 'end_time': end_time})

    return result


def _time_in_slots(target_time, slots):
    for slot in slots:
        if slot['start_time'] <= target_time < slot['end_time']:
            return True
    return False


def resolve_therapist_schedule_for_date(therapist, target_date: date) -> dict:
    day_of_week = target_date.weekday()
    weekly_slots = TherapistWeeklyAvailability.objects.filter(
        therapist=therapist,
        day_of_week=day_of_week,
        is_active=True,
    ).order_by('start_time')

    if weekly_slots.exists():
        base_slots = [
            {
                'start_time': row.start_time,
                'end_time': row.end_time,
                'source': 'weekly',
            }
            for row in weekly_slots
        ]
    else:
        base_slots = [
            {
                'start_time': DEFAULT_AVAILABLE_START_TIME,
                'end_time': DEFAULT_AVAILABLE_END_TIME,
                'source': 'default',
            }
        ]

    available_intervals = [
        {'start_time': slot['start_time'], 'end_time': slot['end_time']}
        for slot in base_slots
    ]
    available_intervals = _merge_intervals(available_intervals)

    overrides = TherapistDateOverride.objects.filter(
        therapist=therapist,
        date=target_date,
        is_active=True,
    ).order_by('start_time')
    has_override = overrides.exists()

    for override in overrides:
        if override.override_type == TherapistDateOverride.OverrideType.UNAVAILABLE:
            available_intervals = _subtract_interval(
                available_intervals,
                override.start_time,
                override.end_time,
            )
        elif override.override_type == TherapistDateOverride.OverrideType.AVAILABLE:
            available_intervals.append(
                {
                    'start_time': override.start_time,
                    'end_time': override.end_time,
                }
            )
            available_intervals = _merge_intervals(available_intervals)

    slots = [
        {
            'start_time': interval['start_time'],
            'end_time': interval['end_time'],
            'status': 'available',
            'source': 'override' if has_override else ('weekly' if weekly_slots.exists() else 'default'),
        }
        for interval in available_intervals
        if interval['start_time'] < interval['end_time']
    ]

    unavailable_slots = []
    for override in overrides:
        if override.override_type == TherapistDateOverride.OverrideType.UNAVAILABLE:
            unavailable_slots.append(
                {
                    'start_time': override.start_time,
                    'end_time': override.end_time,
                    'status': 'unavailable',
                    'source': 'override',
                }
            )

    all_slots = sorted(slots + unavailable_slots, key=lambda x: x['start_time'])

    return {
        'date': target_date,
        'source': 'override' if has_override else ('weekly' if weekly_slots.exists() else 'default'),
        'off': len(slots) == 0,
        'slots': all_slots,
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

    resolved = resolve_therapist_schedule_for_date(profile, treatment_date)
    available_slots = [slot for slot in resolved['slots'] if slot.get('status') == 'available']

    if not available_slots:
        return False

    return _time_in_slots(treatment_time, available_slots)
