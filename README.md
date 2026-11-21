# Library System — Merged Project
Student 1: **Member Information** (`members`) and **Book Categories** (`categories`).
Student 2: **Borrowing Record** and **Return Records & Fine** (`borrowing`).
Student 3: **Appointment Record** (`appointments`) and **Library Admin & User Account** (`accounts`).

## Run
    pip install django            # (+ mysqlclient only if using MySQL)
    python manage.py migrate
    python manage.py seed_demo    # optional demo data
    python manage.py runserver    # http://127.0.0.1:8000/
    python manage.py test         # 61 tests

MySQL: set env vars `DB_ENGINE=mysql DB_NAME=library_db DB_USER=root DB_PASSWORD=...` before migrate.

## Function table -> URL
| Function | URL |
|---|---|
| Register New Member | /members/register/ |
| Update Member Profile | /members/<id>/edit/ |
| View Member History | /members/<id>/history/ |
| Deactivate Account (+ Reactivate, Delete inactive member) | /members/ (buttons) |
| Add New Category | /categories/add/ |
| Edit Category Details (+ remove book, delete category) | /categories/<id>/edit/ |
| Assign Book to Category | /categories/assign/ |
| Checkout Book | /borrowing/checkout/ |
| Renew Loan | /borrowing/renew/ |
| View Active Loans | /borrowing/ |
| Search Borrowing History | /borrowing/history/ |
| Process Book Return | /borrowing/return/ |
| Record Fine Payment | /borrowing/fine-payment/ |
| Generate Fine Report | /borrowing/fine-report/ |
| List Books by Category | /categories/<id>/books/ |

## Integration notes for teammates
- `members.Member` is the shared member table. Student 2/3 should use `ForeignKey('members.Member')` and check `member.is_active` before allowing a loan/reservation.
- `Member.loan_history()` / `has_unreturned_loans()` / `has_any_loans()` expect Student 2's app `borrowing` with model `Loan` (FK `member`, field `status`, value `'returned'` when back). Rename in `members/models.py` if theirs differs.
- `categories.Book` is a minimal placeholder (title, author, isbn, category). Nobody owns book CRUD in the function table; agree who extends it.

## Membership tiers (added)
Created automatically by migration `members/0003_seed_membership_types` (existing members become Basic):

| Tier | Books at a time | Days per loan |
|---|---|---|
| Basic | 3 | 14 |
| Silver | 6 | 21 |
| Gold | 10 | 30 |

Edit or add tiers at `/admin/` (Membership types). For Student 2 (Borrowing):
`member.max_books`, `member.loan_days`, `member.active_loan_count()`, `member.remaining_quota()`, `member.can_borrow()`.
When issuing a loan: block if `not member.can_borrow()`, and set `due_date = today + timedelta(days=member.loan_days)`.

## Upgrading an existing copy
Copy the new `members`, `categories`, `templates`, `static`, `library_system` folders over the old ones (do NOT delete your `db.sqlite3`), then run `python manage.py migrate`.
The UI loads Bootstrap from a CDN, so the browser needs internet access.

## Student 3 modules

### First run (IMPORTANT: every page now requires login)
    python manage.py migrate
    python manage.py runserver
Open http://127.0.0.1:8000/ -> "Create the first administrator" (only offered while no account exists).
Optional demo data: `python manage.py seed_demo` creates accounts admin / Admin@12345, librarian / Library@12345,
assistant / Assist@12345 (demo only: delete them before submitting a real system) plus time slots and one appointment.

### Library Admin & User Account (`accounts`)
| Function | Where |
|---|---|
| Create Account & Assign Roles | Admin > Accounts (/accounts/) : create (temporary password shown once, must be changed at first login), edit role, deactivate/reactivate. The last active administrator is protected. |
| Password Reset & Recovery | Login > "Forgot your password?" (1-hour single-use link; printed in the terminal, and shown on screen in DEBUG demo mode) + Admin "Reset password" (temporary password) + Change password |
| Manage Permissions | Admin > Roles & Permissions (/accounts/roles/) : tick permissions per role; roles Administrator / Librarian / Assistant are preloaded; Administrator cannot be renamed, deleted or lose `accounts.manage` |
| View System Audit Logs | Admin > Audit Log (/accounts/audit/) : filter by text/user/action/date, pagination, CSV export. Logins, failed logins, every create/update/delete (with old -> new values), role and password events are recorded automatically. Passwords are never logged. |

Permissions are enforced for every page by `accounts/middleware.py` (rule table in `accounts/rights.py`):
`members.view|manage`, `categories.view|manage`, `appointments.view|manage`, `accounts.manage`, `audit.view`.

### Appointment Record (`appointments`)
| Function | Where |
|---|---|
| Schedule Reservation | Appointments > Schedule Reservation. Checks: member active, slot open/not started/not full, no double-booking or overlapping time, max upcoming appointments by tier (Basic 2, Silver 3, Gold 4), book required only for "Book pickup". |
| Cancel Appointment | "Cancel" on an upcoming appointment, optional reason; frees the seat. Started/cancelled ones cannot be cancelled. |
| View Upcoming Appointments | /appointments/ : Upcoming / Past / Cancelled / All tabs, member and date filters, today / 7-day counts. |
| Manage Time Slots | /appointments/slots/ : add, edit, close/reopen, delete. Within opening hours 08:00-20:00, min 15 min, capacity 1-20, no overlap, cannot reduce capacity below bookings, cannot delete a slot that has appointment records. |

Integration: appointments use `members.Member` (tier decides the limit) and optionally `categories.Book`; a member with upcoming
appointments cannot be deactivated, and one with appointment records cannot be deleted.

## Upgrading an existing copy
Copy over `members`, `categories`, `accounts`, `appointments`, `templates`, `static`, `library_system` (keep your db.sqlite3), then `python manage.py migrate`.
The first page you open will ask you to log in; if no account exists, use the "Create the first administrator" link.


## Student 3 CRUD additions
- User Accounts: Administrator can permanently delete another account from Admin > Accounts. A confirmation page is shown; the logged-in account and the last active Administrator are protected. The deletion is recorded in the Audit Log.
- Appointment Records: only cancelled appointments can be permanently deleted; upcoming booked appointments must be cancelled first. This protects active reservations and avoids accidental deletion.
- CSV reports: export the currently filtered User Accounts list from Admin > Accounts, and export the currently filtered Appointment list from Appointments. UTF-8 BOM is included for Excel compatibility.


## Combined Dashboard & Analytics (Student 3 enhancement)
The home Dashboard now combines the Student 3 modules and updates directly from database records:
- Appointment Record: total, upcoming, booked and cancelled appointment counts, a 7-day appointment trend chart, and recently created appointments.
- Library Admin & User Account: total, active and inactive account counts, a role distribution chart, and recent audit activities (when the signed-in role has `audit.view`).
- Dashboard sections respect role permissions: appointment statistics require `appointments.view`; account statistics require `accounts.manage`; audit activity requires `audit.view`.
- Charts use Chart.js from a CDN, so an internet connection is needed to render charts. The summary numbers and tables still render without the chart library.

## Permanent User Account Deletion
Administrators can permanently delete another user from Admin > Accounts > Delete. The action requires a confirmation POST, cannot delete the signed-in account or the last active administrator, and writes an `account_delete` audit record before removing the account. Audit history retains the deleted actor/target username text.


## Public member registration and sign-in
- The root URL (`/`) is a public landing page with a catalogue preview.
- Visitors can register at `/accounts/register/`. Registration creates both a Django login account (with a hashed password) and a linked library member record.
- Users sign in at `/accounts/login/`; authenticated users can open `/dashboard/`.
- Staff account creation is no longer exposed as a separate Create Account screen. Staff roles can still be assigned to existing accounts by administrators. The first Administrator can still be created through first-run setup, even if member accounts were registered beforehand.
- This ZIP does not contain a Borrowing app/model or borrowing pages. The authentication foundation is in place, but borrowing workflows must be integrated from the borrowing module before book loans can be made.


## Student 2 modules — Borrowing Record and Return Records & Fine (`borrowing`)
| Function | Where |
|---|---|
| Checkout Book | Borrowing > Checkout Book. Selects an active member and available book; due date is calculated from the member's membership tier. |
| Renew Loan | Borrowing > Renew Loan. Each loan may be renewed once; extension uses the member's tier loan period. |
| View Active Loans | Borrowing > Active Loans. Shows current checkouts and supports search by member, email, title or ISBN. |
| Search Borrowing History | Borrowing > Borrowing History. Search all active and returned loan records by member or book. |
| Process Book Return | Borrowing > Process Book Return. Calculates overdue days and fine before confirmation; default fine rate is RM1.00 per overdue day and can be changed on the form. |
| Calculate Late Fine | Calculated when a return is processed: max(return date - due date, 0) × daily fine rate. |
| Record Fine Payment | Borrowing > Record Fine Payment. Supports partial or full payment, payment method and reference; prevents overpayment. |
| Generate Fine Report | Borrowing > Fine Report. Date filters, total fines assessed, payments received, outstanding balance and transaction list. |

Borrowing uses the shared `members.Member` and `categories.Book` records. A member must be active and below their membership-tier book limit to check out a book. A book cannot have more than one active loan. Returned loans and fine-payment records are retained for history/reporting.
