import logging
import math
from datetime import date
from django.db import transaction
from django.db.models import Sum, Count, F, Q

from booking.models import Booking
from inventory.models import Inventory, TherapistSupplyAssignment, SupplyUsageLog
from layanan.models import LayananSupplyConfig

logger = logging.getLogger(__name__)


def record_supply_usage_for_completed_booking(booking: Booking) -> bool:
    """
    Called when a booking status transitions to COMPLETED.
    - Reads required supply from booking.layanans
    - Creates SupplyUsageLog per item
    - Deducts remaining_usage from TherapistSupplyAssignment with FIFO strategy
    """
    # 1. Skip if no therapist
    if not booking.therapist_id:
        logger.warning(
            f"Booking {booking.booking_id} completed but has no therapist. "
            "Supply usage logging skipped."
        )
        return False

    # 2. Collect item requirements from multiple layanans
    layanans = booking.layanans.all()
    if not layanans:
        logger.info(f"Booking {booking.booking_id} has no layanans mapped. Skipping supply usage.")
        return False

    # Aggregate total jumlah_per_use per item required
    item_requirements = {}
    for layanan in layanans:
        configs = LayananSupplyConfig.objects.filter(layanan=layanan, is_deleted=False).select_related('item')
        for config in configs:
            item_id = config.item_id
            if item_id not in item_requirements:
                item_requirements[item_id] = {
                    'item': config.item,
                    'total_jumlah': 0
                }
            item_requirements[item_id]['total_jumlah'] += config.jumlah_per_use

    if not item_requirements:
        return False

    user_therapist = booking.therapist
    tanggal_treatment = booking.tgl_treatment

    try:
        therapist_profile = user_therapist.therapist_profile
    except Exception:
        logger.warning(f"Booking {booking.booking_id} user doesn't have Therapist profile.")
        return False

    # 3. Process each item requirement inside an atomic transaction
    with transaction.atomic():
        for item_id, req in item_requirements.items():
            item = req['item']
            jumlah_required = req['total_jumlah']

            # Idempotency check: if already logged for this booking, item, therapist
            if SupplyUsageLog.objects.filter(booking=booking, item=item, therapist=therapist_profile).exists():
                logger.info(
                    f"SupplyUsageLog already exists for Booking {booking.booking_id}, "
                    f"Item {item.nama_barang}, Therapist {therapist_profile.name}. Skipping."
                )
                continue

            # Create log first
            SupplyUsageLog.objects.create(
                item=item,
                therapist=therapist_profile,
                jumlah=jumlah_required,
                tanggal=tanggal_treatment,
                booking=booking
            )

            # Deduct FIFO from active assignments
            active_assignments = TherapistSupplyAssignment.objects.select_for_update().filter(
                therapist=therapist_profile,
                item=item,
                status=TherapistSupplyAssignment.Status.ACTIVE,
                is_deleted=False
            ).order_by('assigned_at')

            remaining_to_deduct = jumlah_required

            for assignment in active_assignments:
                if remaining_to_deduct <= 0:
                    break

                if assignment.remaining_usage <= remaining_to_deduct:
                    # Exhaust this assignment
                    remaining_to_deduct -= assignment.remaining_usage
                    assignment.remaining_usage = 0
                    assignment.status = TherapistSupplyAssignment.Status.EXHAUSTED
                else:
                    # Partially consume this assignment
                    assignment.remaining_usage -= remaining_to_deduct
                    remaining_to_deduct = 0

                assignment.save(update_fields=['remaining_usage', 'status', 'updated_at'])

            if remaining_to_deduct > 0:
                logger.warning(
                    f"Therapist {therapist.name} used {jumlah_required} of {item.nama_barang} "
                    f"but active assignments fell short by {remaining_to_deduct}."
                )

    return True


def calculate_supply_tracker(start_date=None, end_date=None, item_id=None, therapist_id=None):
    """
    Tracker Service Kalkulasi.
    Returns: {
        "riwayatPemakaian": [],
        "summaryPerItem": [],
        "rankingPenggunaanPerTherapist": [],
        "assignmentSummary": []
    }
    """
    # Base Query for logs
    qs_logs = SupplyUsageLog.objects.select_related('item', 'therapist').all()
    
    if start_date:
        qs_logs = qs_logs.filter(tanggal__gte=start_date)
    if end_date:
        qs_logs = qs_logs.filter(tanggal__lte=end_date)
    if item_id:
        qs_logs = qs_logs.filter(item_id=item_id)
    if therapist_id:
        qs_logs = qs_logs.filter(therapist_id=therapist_id)

    # 1. riwayatPemakaian
    riwayat_pemakaian = []
    for log in qs_logs.order_by('-tanggal', '-created_at'):
        riwayat_pemakaian.append({
            "itemId": log.item_id,
            "therapistId": log.therapist_id,
            "jumlah": log.jumlah,
            "tanggal": log.tanggal.strftime("%Y-%m-%d") if log.tanggal else None
        })

    # 2. summaryPerItem
    summary_per_item = []
    # Calculate totals per item
    item_stats = qs_logs.values('item_id').annotate(
        total_terpakai=Sum('jumlah'),
        hari_aktif=Count('tanggal', distinct=True)
    )

    item_ids = [stat['item_id'] for stat in item_stats]
    items = Inventory.objects.filter(id__in=item_ids) if item_ids else []
    item_dict = {i.id: i for i in items}

    today = date.today()

    for stat in item_stats:
        i_id = stat['item_id']
        t_terpakai = stat['total_terpakai'] or 0
        h_aktif = stat['hari_aktif'] or 0
        
        rata_rata = (t_terpakai / h_aktif) if h_aktif > 0 else 0
        
        inv_item = item_dict.get(i_id)
        stok_saat_ini = inv_item.jumlah_stok if inv_item else 0
        
        if rata_rata > 0:
            sisa_hari = math.floor(stok_saat_ini / rata_rata)
            estimasi_habis = str(date.fromordinal(today.toordinal() + sisa_hari))
        else:
            estimasi_habis = None

        summary_per_item.append({
            "itemId": i_id,
            "totalTerpakai": t_terpakai,
            "rataRataPemakaianHarian": round(rata_rata, 2),
            "stokSaatIni": stok_saat_ini,
            "estimasiHabis": estimasi_habis
        })
        
    # Sort summary by itemId for consistency
    summary_per_item.sort(key=lambda x: x['itemId'])

    # 3. rankingPenggunaanPerTherapist
    # Note: Using tie-breaker therapist_id asc
    therapist_stats = qs_logs.values('therapist_id').annotate(
        total_pemakaian=Sum('jumlah')
    ).order_by('-total_pemakaian', 'therapist_id')

    ranking_penggunaan = []
    for rank, stat in enumerate(therapist_stats, start=1):
        ranking_penggunaan.append({
            "therapistId": stat['therapist_id'],
            "totalPemakaian": stat['total_pemakaian'] or 0,
            "rank": rank
        })

    # 4. assignmentSummary
    qs_assignments = TherapistSupplyAssignment.objects.filter(is_deleted=False)
    if item_id:
        qs_assignments = qs_assignments.filter(item_id=item_id)
    if therapist_id:
        qs_assignments = qs_assignments.filter(therapist_id=therapist_id)

    assignment_summary = []
    for assgn in qs_assignments.order_by('-assigned_at'):
        assignment_summary.append({
            "assignmentId": assgn.id,
            "itemId": assgn.item_id,
            "therapistId": assgn.therapist_id,
            "quantityAssigned": assgn.quantity_assigned,
            "usagePerUnit": assgn.usage_per_unit,
            "totalUsage": assgn.total_usage,
            "remainingUsage": assgn.remaining_usage,
            "status": assgn.status
        })

    return {
        "riwayatPemakaian": riwayat_pemakaian,
        "summaryPerItem": summary_per_item,
        "rankingPenggunaanPerTherapist": ranking_penggunaan,
        "assignmentSummary": assignment_summary
    }
