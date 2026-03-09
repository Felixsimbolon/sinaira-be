# 📌 Membership & Loyalty Feature

## 👤 Developer Information
Nama  : Ezar Akhdan Shada Surahman
NPM   : 2306165894
Branch: feat/ezar

---

# 📖 Feature Overview

Fitur **Manajemen Membership & Loyalty** menyediakan sistem untuk:

1. Customer melakukan pengecekan status membership.
2. Admin/Supervisor/Owner memantau loyalitas customer melalui admin panel.

Fitur ini menghitung membership berdasarkan jumlah booking dengan status `completed`.

Milestone reward ditentukan pada booking ke-4, ke-7, dan ke-10.

---

# 🎯 Scope of Work

## 1️⃣ Customer Check Membership

Customer dapat:
- Memasukkan nomor telepon yang digunakan saat booking
- Melihat:
  - Nama customer
  - Total booking completed
  - Progress milestone (4, 7, 10)
  - Informasi milestone yang telah tercapai
  - Riwayat booking

Fitur ini tidak memerlukan login.

---

## 2️⃣ Membership & Loyalty Tracker (Admin Panel)

Admin, Supervisor, dan Owner dapat:
- Melihat tabel membership berisi:
  - Nama
  - Nomor Telepon
  - Total Booking (completed)
  - Total Pembayaran
  - Layanan Terbanyak
- Melakukan:
  - Search
  - Filter
  - Sorting
  - Export CSV
- Melihat detail membership customer (halaman terpisah)

Data bersifat read-only dan dihitung otomatis dari riwayat booking.
