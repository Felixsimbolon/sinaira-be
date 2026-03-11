# Testing the API with Postman

## 1. Start the server

```bash
cd senaira-be/senairabe-backend
source venv/bin/activate
python manage.py runserver
```

Base URL: **http://127.0.0.1:8000**

## 2. Create a superuser (one-time)

The therapists API requires a user with Supervisor/Owner role. Easiest is a superuser:

```bash
python manage.py createsuperuser
# Enter username, email, password
```

## 3. Get an auth token

**Request**

- Method: **POST**
- URL: `http://127.0.0.1:8000/api/auth/token/`
- Body: **raw** → **JSON**

```json
{
  "username": "your_superuser_username",
  "password": "your_password"
}
```

**Response**

```json
{
  "token": "abc123..."
}
```

Copy the `token` value.

## 4. Call the therapists API

For every therapists request, set the header:

- Key: **Authorization**
- Value: **Token \<paste your token here\>**

Example: `Token abc123def456...`

### Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | http://127.0.0.1:8000/api/therapists/ | List active therapists |
| POST | http://127.0.0.1:8000/api/therapists/ | Create therapist (JSON body) |
| GET | http://127.0.0.1:8000/api/therapists/1/ | Get therapist by id |
| PATCH | http://127.0.0.1:8000/api/therapists/1/ | Update therapist (partial) |
| PUT | http://127.0.0.1:8000/api/therapists/1/ | Full update |
| DELETE | http://127.0.0.1:8000/api/therapists/1/ | Soft delete (sets is_active=false) |

### Example: Create therapist (POST body)

```json
{
  "name": "Dr. Jane Doe",
  "email": "jane@therapist.com",
  "license_number": "LIC-001",
  "phone_number": "+62812345678",
  "specialization": "Anxiety"
}
```

## 5. Alternative: Basic Auth in Postman

Instead of token, you can use **Basic Auth** in Postman:

- Auth tab → Type: **Basic Authentication**
- Username: your superuser username  
- Password: your password  

No need to call `/api/auth/token/` in that case.
