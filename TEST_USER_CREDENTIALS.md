# Test User Credentials

This file lists the current users found in the local database and the known seeded/test passwords.

Important: Django stores passwords as hashes, so plaintext passwords cannot be read back from the database. Passwords are only listed here when they are known from seed scripts or from test users created manually.

## Current Local Users

| Username | Email | Role | Active | Superuser | Known Password |
|---|---|---|---|---|---|
| `Blessing` | `bjmbalaka@gmail.com` | Admin | Yes | Yes | Unknown locally. Reset if needed. |
| `Financial` | `financial@gmail.com` | Dean | Yes | No | Unknown locally. Reset if needed. |
| `Test` | `test@gmail.com` | Project Manager | Yes | No | Unknown locally. Reset if needed. |
| `test_centre_head` | `test_centre_head@example.com` | Centre Head | Yes | No | `TestCentreHead123!` |
| `test_dean` | `test_dean@example.com` | Dean | Yes | No | `TestDean123!` |

## Seeded Credentials Found In Repo

These users are created by `users/management/commands/inject_fake_users.py` when that command is run.

| Username | Email | Role | Password |
|---|---|---|---|
| `test_admin` | `admin@testproject.com` | Admin | `TestPass123` |
| `test_supervisor` | `supervisor@testproject.com` | Supervisor | `TestPass123` |
| `test_manager` | `manager@testproject.com` | Project Manager | `TestPass123` |
| `test_financialadmin` | `financialadmin@testproject.com` | Financial Admin | `TestPass123` |
| `test_staff` | `staff@testproject.com` | Staff | `TestPass123` |
| `test_student` | `student@testproject.com` | Student | `TestPass123` |

The default admin seeders create this user:

| Username | Email | Role | Password |
|---|---|---|---|
| `Admin` | `lotriet.work@gmail.com` | Admin | `User.1234` |

The supervisor/student test script `fix scripts/create_test_users.py` uses:

| Username | Role | Password |
|---|---|---|
| `prof_muranga` | Supervisor | `TestPass123!` |
| `prof_adeyemi` | Supervisor | `TestPass123!` |
| `prof_okonkwo` | Supervisor | `TestPass123!` |
| `student_test1` | Student | `StudentPass123!` |
| `student_test2` | Student | `StudentPass123!` |
| `student_test3` | Student | `StudentPass123!` |

## Reset Current Local Passwords

Run this if you want every current local user to have a known password:

```powershell
.\.venv\Scripts\python.exe manage.py shell
```

```python
from users.models import CustomUser

passwords = {
    "Blessing": "Admin123!",
    "Financial": "Dean123!",
    "Test": "Manager123!",
    "test_dean": "TestDean123!",
    "test_centre_head": "TestCentreHead123!",
}

for username, password in passwords.items():
    user = CustomUser.objects.get(username=username)
    user.set_password(password)
    user.save()
    print(f"{username}: {password}")
```

