# Backlog — Inventory & Therapist Supply Request

## Dhania Tiaraputri Herdiani - 2306165881

---

## Fitur yang akan Dikerjakan

---

### PBI-15 — Read Inventory List (SP 1)

**Role:** Supervisor

Menampilkan seluruh data inventori alat spa dalam tabel terpusat untuk monitoring stok operasional.

**To-Do:**
- Buat model Inventory (namaBarang, kategori, jumlahStok, status, isActive)
- Implement soft delete field (isActive)
- Buat serializer Inventory
- Buat endpoint `GET /api/inventory`
- Filter hanya item aktif
- Return response `200 OK`
- Tambahkan pagination jika diperlukan

---

### PBI-16 — Create Inventory Item (SP 2)

**Role:** Supervisor

Menambahkan item inventori baru melalui form input.

**To-Do:**
- Buat endpoint `POST /api/inventory`
- Validasi field wajib (namaBarang, kategori, jumlahStok)
- Validasi jumlahStok tidak boleh negatif
- Simpan data ke PostgreSQL
- Return response `201 Created`
- Tambahkan permission role Supervisor

---

### PBI-17 — Update Inventory Item (SP 2)

**Role:** Supervisor

Mengubah data inventori agar informasi tetap akurat.

**To-Do:**
- Buat endpoint `PUT /api/inventory/{id}`
- Validasi item berdasarkan ID
- Update data inventori di database
- Return response `200 OK`
- Tambahkan permission role Supervisor

---

### PBI-18 — Delete Inventory Item (SP 1)

**Role:** Supervisor

Menghapus item inventori dengan mekanisme soft delete.

**To-Do:**
- Buat endpoint `DELETE /api/inventory/{id}`
- Implement soft delete (isActive = false)
- Pastikan item tidak hilang dari database
- Return response `200 OK`

---

### PBI-19 — Low Stock Indicator (SP 3)

**Role:** Supervisor

Memberikan indikator stok rendah untuk tindakan cepat.

**To-Do:**
- Tambahkan field threshold minimum stok pada model
- Buat fungsi perhitungan status stok (Normal / Low)
- Tambahkan status stok pada serializer response
- Pastikan status ikut ditampilkan di API

---

### PBI-20 — Create Supply Request (SP 2)

**Role:** Therapist

Mengajukan permintaan alat melalui form sistem.

**To-Do:**
- Buat model SupplyRequest (item, quantity, reason, status, createdBy)
- Status default `Pending`
- Buat serializer SupplyRequest
- Buat endpoint `POST /api/supply-request`
- Validasi quantity > 0
- Return response `201 Created`
- Tambahkan permission role Therapist

---

### PBI-21 — Read Supply Request List (SP 1)

**Role:** Supervisor

Melihat seluruh permintaan alat yang masuk.

**To-Do:**
- Buat endpoint `GET /api/supply-request`
- Implement filter berdasarkan role
- Supervisor melihat semua request
- Return response `200 OK`

---

### PBI-22 — Approve / Reject Supply Request (SP 3)

**Role:** Supervisor

Menyetujui atau menolak permintaan alat.

**To-Do:**
- Buat endpoint `PATCH /api/supply-request/{id}`
- Update status menjadi `Approved` atau `Rejected`
- Validasi hanya Supervisor yang dapat melakukan aksi
- Simpan timestamp approval
- Return response `200 OK`

---

### PBI-23 — Update Inventory After Approval (SP 3)

**Role:** System

Mengurangi stok inventori otomatis setelah request disetujui.

**To-Do:**
- Gunakan transaction atomic Django
- Jika status `Approved` → kurangi stok inventory
- Validasi stok tidak boleh minus
- Simpan history perubahan stok
- Rollback transaksi jika terjadi error