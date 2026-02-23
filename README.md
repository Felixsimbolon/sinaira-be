# SINAIRA Backend

Backend API untuk Sistem Informasi Sineira Homespa menggunakan Django REST Framework.

## Struktur Direktori

```
sinaira-be/
├── config/              # Konfigurasi Django
│   ├── __init__.py
│   ├── settings.py      # Settings utama Django
│   ├── urls.py          # URL routing
│   ├── asgi.py          # ASGI configuration
│   └── wsgi.py          # WSGI configuration
├── env/                 # Virtual environment (tidak di-commit)
├── manage.py            # Django management script
├── requirements.txt     # Python dependencies
├── db.sqlite3           # SQLite database (development)
└── .gitignore           # Git ignore file
```

## Prerequisites

- Python 3.12+
- pip (Python package manager)
- PostgreSQL (untuk production, opsional untuk development)

## Setup & Installation

### 1. Clone Repository

```bash
git clone https://gitlab.cs.ui.ac.id/propensi-2025-2026-genap/kelas-b/proper/senairabe-backend.git
cd sinaira-be
```

### 2. Virtual Environment

**macOS/Linux:**
```bash
python3 -m venv env
source env/bin/activate
```

**Windows:**
```bash
python -m venv env
env\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Database

Untuk development, proyek ini menggunakan SQLite. Untuk production, PostgreSQL.

```bash
python manage.py migrate
```

### 5. Buat Superuser (Opsional)

```bash
python manage.py createsuperuser
```

### 6. Jalankan Development Server

```bash
python manage.py runserver
```

Server akan berjalan di `http://localhost:8000`

## Tech Stack

- **Django 6.0.2** - Web framework
- **Django REST Framework 3.16.1** - REST API framework
- **django-cors-headers 4.9.0** - CORS handling untuk frontend
- **django-environ 0.13.0** - Environment variable management
- **psycopg2-binary 2.9.11** - PostgreSQL adapter
- **SQLite** - Database development


## Development Commands

### Menjalankan Migration
```bash
python manage.py makemigrations
python manage.py migrate
```

### Membuat App Baru
```bash
python manage.py startapp <app_name>
```

### Menjalankan Tests
```bash
python manage.py test
```

### Membuat Requirements File
```bash
pip freeze > requirements.txt
```

## CORS Configuration

CORS sudah dikonfigurasi untuk menerima request dari frontend Vue.js yang berjalan di `http://localhost:5173`. Untuk menambahkan origin lain, edit `CORS_ALLOWED_ORIGINS` di `config/settings.py`.

## Database

### Development
Menggunakan SQLite (`db.sqlite3`) - sudah dikonfigurasi secara default.

### Production
Gunakan PostgreSQL dengan mengatur `DATABASE_URL` di environment variables.

## Notes

- File `env/` dan `db.sqlite3` tidak di-commit ke repository
- Pastikan virtual environment selalu aktif saat development
- Untuk production, gunakan PostgreSQL dan set `DEBUG=False`
- Update `requirements.txt` setiap menambah package baru
