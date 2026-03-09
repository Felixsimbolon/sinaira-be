# 📌 Booking Management Feature

## 👤 Developer Information
Nama  : Gnade Yuka
NPM   : 2306165704  
Branch: feat/yuka  

---

# 📖 Feature Overview

Fitur **Booking Management** menyediakan sistem pemesanan layanan home spa yang terintegrasi untuk customer dan admin.

Fitur ini memungkinkan:

1. Customer melakukan booking layanan melalui website atau WhatsApp.
2. Sistem menyimpan dan mengelola data booking secara terpusat.
3. Admin mengelola status booking dan penugasan therapist.
4. Sistem mempercepat proses input booking WhatsApp melalui parsing otomatis.

Booking memiliki alur status:

Need Confirmation → Confirmed → Assigned → Paid → Finished  
Tambahan: Cancelled dan Rejected.



---

# 🎯 Scope of Work

## 1️⃣ Create Booking by Customer

### Website Booking
Customer dapat:
- Mengisi nomor telepon tanpa login
- Mengisi detail booking:
  - alamat
  - tanggal & waktu
  - layanan
  - jumlah therapist
  - voucher (opsional)
  - catatan tambahan
- Melihat estimasi biaya
- Mengirim booking yang langsung tersimpan di sistem
- Mendapatan ID booking untuk referensi

### WhatsApp Booking
Customer dapat:
- Menekan tombol WhatsApp
- Mengirim template pesan booking otomatis ke admin

---

## 2️⃣ Booking Management (Admin Panel)

Admin dapat:
- Melihat seluruh booking dalam tabel terpusat
- Mengelola status booking sesuai alur layanan
- Menambahkan booking dari WhatsApp
- Melakukan pencarian, filter, dan sorting
- Membuka detail booking lengkap

Sistem mencatat timestamp dan riwayat perubahan untuk audit dan tracking.

---

## 3️⃣ Booking Detail & Activity Tracking

Admin dapat melihat:
- Informasi lengkap booking
- Data customer dan layanan
- Therapist yang ditugaskan
- Riwayat perubahan status
- Catatan aktivitas booking

Booking yang dibatalkan tetap tersimpan di database.

---

## 4️⃣ Therapist Assignment & Availability Check

Admin dapat:
- Melihat therapist yang tersedia berdasarkan jadwal
- Menugaskan therapist sesuai kebutuhan layanan
- Menghindari double booking
- Mengubah assignment sebelum layanan selesai

Therapist menerima notifikasi penugasan beserta detail booking.

---

## 5️⃣ WhatsApp Booking Auto-Generate Parser

Admin dapat:
- Menyalin template pesan booking
- Sistem mengekstrak data otomatis
- Melihat preview hasil parsing
- Mengedit sebelum menyimpan booking

Fitur ini mengurangi kesalahan input manual dan mempercepat proses administrasi.