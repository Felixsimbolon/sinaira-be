from collections import Counter
from decimal import Decimal

from django.db.models import Count, Q, Sum

from booking.models import Booking


MILESTONES = [4, 7, 10]
SUPPORTED_SUMMARY_ORDERING = {
    'totalBooking',
    '-totalBooking',
    'totalPembayaran',
    '-totalPembayaran',
}


class CustomerNotFoundError(Exception):
    """Raised when no bookings exist for the given phone number."""


def calculate_membership_progress(total_completed_bookings):
    milestones_achieved = [
        milestone
        for milestone in MILESTONES
        if total_completed_bookings >= milestone
    ]
    next_milestone = next(
        (
            milestone
            for milestone in MILESTONES
            if total_completed_bookings < milestone
        ),
        None,
    )
    remaining_to_next_milestone = (
        next_milestone - total_completed_bookings
        if next_milestone is not None
        else 0
    )

    return milestones_achieved, next_milestone, remaining_to_next_milestone


def get_membership_status(phone_number):
    customer_bookings = Booking.objects.filter(no_hp=phone_number)
    if not customer_bookings.exists():
        raise CustomerNotFoundError

    completed_bookings = Booking.objects.filter(
        no_hp=phone_number,
        status=Booking.BookingStatus.COMPLETED,
    )
    total_completed_bookings = completed_bookings.count()

    milestones_achieved, next_milestone, remaining_to_next_milestone = (
        calculate_membership_progress(total_completed_bookings)
    )

    latest_customer_booking = customer_bookings.order_by('-tgl_treatment', '-jam_treatment').first()
    latest_completed_bookings = completed_bookings.order_by('-tgl_treatment', '-jam_treatment')[:5]

    return {
        'namaCustomer': latest_customer_booking.nama,
        'phoneNumber': phone_number,
        'totalBookingCompleted': total_completed_bookings,
        'milestonesAchieved': milestones_achieved,
        'nextMilestone': next_milestone,
        'remainingToNextMilestone': remaining_to_next_milestone,
        'bookingHistory': [
            {
                'bookingId': booking.booking_id,
                'tanggal': booking.tgl_treatment.isoformat(),
                'layanan': booking.perawatan_pilihan,
                'status': booking.status,
            }
            for booking in latest_completed_bookings
        ],
    }


def _split_layanan(value):
    return [
        item.strip()
        for item in (value or '').split(',')
        if item.strip()
    ]


def _decimal_to_number(value):
    if value is None:
        return 0

    if not isinstance(value, Decimal):
        value = Decimal(value)

    if value == value.to_integral_value():
        return int(value)

    return float(value)


def get_membership_summary(search=None, min_booking=None, ordering=None):
    bookings = Booking.objects.filter(
        status=Booking.BookingStatus.COMPLETED,
    )

    if search:
        bookings = bookings.filter(
            Q(nama__icontains=search) | Q(no_hp__icontains=search)
        )

    aggregated_rows = list(
        bookings.values('no_hp')
        .annotate(
            totalBooking=Count('id'),
            totalPembayaran=Sum('total_pembayaran'),
        )
        .exclude(no_hp__isnull=True)
        .exclude(no_hp='')
    )

    if min_booking is not None:
        aggregated_rows = [
            row
            for row in aggregated_rows
            if row['totalBooking'] >= min_booking
        ]

    phone_numbers = [row['no_hp'] for row in aggregated_rows]
    booking_rows = bookings.filter(no_hp__in=phone_numbers).only(
        'no_hp',
        'nama',
        'perawatan_pilihan',
        'created_at',
    ).order_by('no_hp', '-created_at')

    latest_name_by_phone = {}
    layanan_counter_by_phone = {}

    for booking in booking_rows:
        if booking.no_hp not in latest_name_by_phone:
            latest_name_by_phone[booking.no_hp] = booking.nama

        counter = layanan_counter_by_phone.setdefault(booking.no_hp, Counter())
        counter.update(_split_layanan(booking.perawatan_pilihan))

    results = []
    for row in aggregated_rows:
        phone_number = row['no_hp']
        layanan_counter = layanan_counter_by_phone.get(phone_number, Counter())
        layanan_terbanyak = layanan_counter.most_common(1)[0][0] if layanan_counter else ''

        results.append({
            'idCustomer': phone_number,
            'namaCustomer': latest_name_by_phone.get(phone_number, ''),
            'nomorTelepon': phone_number,
            'totalBooking': row['totalBooking'],
            'totalPembayaran': _decimal_to_number(row['totalPembayaran']),
            'layananTerbanyak': layanan_terbanyak,
        })

    if ordering in SUPPORTED_SUMMARY_ORDERING:
        reverse = ordering.startswith('-')
        field = ordering[1:] if reverse else ordering
        results.sort(key=lambda item: item[field], reverse=reverse)
    else:
        results.sort(key=lambda item: item['namaCustomer'].lower())

    return results
