from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_id',
        'nama',
        'no_hp',
        'tgl_treatment',
        'jam_treatment',
        'perawatan_pilihan',
        'status',
        'therapist',
        'created_at'
    ]
    list_filter = ['status', 'tgl_treatment', 'aromatherapy_oil']
    search_fields = ['booking_id', 'nama', 'no_hp', 'perawatan_pilihan']
    ordering = ['-tgl_treatment', '-jam_treatment']
    date_hierarchy = 'tgl_treatment'
    
    fieldsets = (
        ('Booking ID', {
            'fields': ('booking_id',)
        }),
        ('Customer Information', {
            'fields': ('user', 'nama', 'alamat', 'kota', 'no_hp')
        }),
        ('Treatment Details', {
            'fields': ('tgl_treatment', 'jam_treatment', 'perawatan_pilihan', 'aromatherapy_oil')
        }),
        ('Special Conditions', {
            'fields': ('kondisi_khusus', 'tahu_dari')
        }),
        ('Assignment & Status', {
            'fields': ('therapist', 'status', 'notes', 'voucher_code')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['booking_id', 'created_at', 'updated_at']

