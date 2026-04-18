from booking.models import Booking


MILESTONES = [4, 7, 10]


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
                'tanggal': booking.tgl_treatment,
                'layanan': booking.perawatan_pilihan,
                'status': booking.status,
            }
            for booking in latest_completed_bookings
        ],
    }
