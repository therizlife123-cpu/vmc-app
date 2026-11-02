# Vidya Mandir Classes (VMC)
### Coaching Center Management System

A web-based coaching center management application built with **Python, Flask, MySQL, Bootstrap, and custom CSS**. VMC helps administrators and teachers manage student records, monitor fee collections, record payments, and generate monthly reports from a centralized dashboard.

---

## Overview

Vidya Mandir Classes (VMC) provides a single place to manage day-to-day coaching center operations. The application uses role-aware access: the primary administrator can manage teacher accounts and view institute-wide student information, while regular teachers work with the students assigned to their account.

## Features

### Dashboard
- View student information and fee-related summaries.
- Search student records.
- Filter dashboard information by month and year.
- View collection and outstanding-fee information.

### Student Management
- Add new students with contact, class, subject, timing, monthly fee, and joining-date details.
- Edit student information.
- Update student status.
- Restrict regular teachers to their own student records.

### Fee & Payment Management
- Track monthly fees and outstanding balances.
- View a dedicated fee dashboard.
- Record full or partial fee payments.
- Allocate payments to the oldest outstanding month first.
- Maintain payment history for students.
- Generate payment receipts.

### Reports
- View monthly fee and collection reports.
- Review payment and outstanding-fee information for reporting.

### Teacher & Account Management
- Administer teacher accounts from the teacher management section.
- Add and edit teacher accounts.
- Activate or deactivate teacher accounts.
- Allow teachers to manage their profile.
- Upload a teacher signature image (PNG, JPG, or JPEG) for use in the application.

### Interface
- Responsive dashboard layout.
- Bootstrap 5 styling with custom CSS.
- Navigation for dashboard, students, fees, teachers, and profile pages.

---

## Technology Stack

| Area | Technology |
|---|---|
| Backend | Python, Flask |
| Database | MySQL |
| Frontend | HTML, CSS, Bootstrap 5 |
| Icons | Font Awesome |
| Authentication | Flask sessions, Werkzeug password hashing |
| Database connector | mysql-connector-python |
| Production server option | Gunicorn |

---

## Project Structure

```text
vmc-app/
├── app.py                         # Flask application, routes and business logic
├── requirements.txt               # Python dependencies
├── README.md                      # Project documentation
├── README_FIXED.md                # Notes about project fixes and fee behavior
├── templates/
│   ├── base.html                  # Shared layout and navigation
│   ├── login.html                 # Login page
│   ├── dashboard.html             # Main dashboard
│   ├── students.html              # Add student form
│   ├── edit_student.html          # Edit student form
│   ├── fee_dashboard.html         # Fee overview
│   ├── pay_fee.html               # Payment form
│   ├── payment_history.html       # Student payment history
│   ├── receipt.html               # Payment receipt
│   ├── monthly_report.html        # Monthly report
│   ├── teachers.html              # Teacher management
│   ├── add_teacher.html           # Add teacher form
│   ├── edit_teacher.html          # Edit teacher form
│   └── profile.html               # Teacher profile and signature
└── static/
    ├── css/
    │   └── style.css              # Application styles
    └── images/
        └── signatures/            # Uploaded teacher signatures
```

---

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.10 or later
- pip
- MySQL Server and access to a MySQL database
- Git

> **Database note:** The current application connects to a MySQL database named `coaching_center`. This repository does not include a database schema or migration script. Before starting the app, configure the existing database and ensure it contains the tables and columns used by the application (including `teachers`, `students`, `fees`, and `payments`).

### 1. Clone the repository

```bash
git clone https://github.com/therizlife123-cpu/vmc-app.git
cd vmc-app
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```bat
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

The application reads its MySQL connection settings and Flask session secret from environment variables.

| Variable | Purpose |
|---|---|
| `MYSQL_HOST` | MySQL server hostname |
| `MYSQL_PORT` | MySQL server port (defaults to `13223` in the current code) |
| `MYSQL_USER` | MySQL username |
| `MYSQL_PASSWORD` | MySQL password |
| `VMC_SECRET_KEY` | Secret key used to sign Flask sessions |

**Windows PowerShell:**

```powershell
$env:MYSQL_HOST = "your_mysql_host"
$env:MYSQL_PORT = "13223"
$env:MYSQL_USER = "your_mysql_username"
$env:MYSQL_PASSWORD = "your_mysql_password"
$env:VMC_SECRET_KEY = "replace_with_a_long_random_secret"
```

**Linux / macOS:**

```bash
export MYSQL_HOST="your_mysql_host"
export MYSQL_PORT="13223"
export MYSQL_USER="your_mysql_username"
export MYSQL_PASSWORD="your_mysql_password"
export VMC_SECRET_KEY="replace_with_a_long_random_secret"
```

Use the port assigned by your MySQL provider; change the example value if your server uses a different port. The database name is currently set to `coaching_center` in `app.py`.

### 5. Run the application

```bash
python app.py
```

Open the application in your browser:

```text
http://127.0.0.1:5000
```

The home page redirects to the login page. Sign in with an account already configured in the `teachers` table.

---

## Main Application Routes

| Route | Purpose |
|---|---|
| `/login` | Teacher/admin login |
| `/logout` | Sign out |
| `/dashboard` | Main dashboard |
| `/students` | Add a student |
| `/edit/<id>` | Edit a student |
| `/delete/<id>` | Delete a student |
| `/toggle_status/<id>` | Change student status |
| `/fees` | Redirect to fee dashboard |
| `/fee_dashboard` | Fee overview |
| `/pay_fee/<id>` | Record a fee payment |
| `/payment_history/<id>` | View payment history |
| `/receipt/<payment_id>` | View a payment receipt |
| `/monthly_report` | Monthly report |
| `/teachers` | Teacher management |
| `/teachers/add` | Add a teacher |
| `/teachers/edit/<id>` | Edit a teacher |
| `/teachers/toggle/<id>` | Activate/deactivate a teacher |
| `/profile` | View profile and upload signature |

---

## Fee Tracking Logic

The application builds a monthly fee ledger from a student's joining month through the selected/current period. It can account for months that do not yet have a corresponding row in the `fees` table.

When a payment is recorded, the application applies it to the oldest outstanding fee first. This helps keep earlier dues settled before newer monthly fees. Payment records are also maintained in the `payments` table for history and receipt views.

For additional implementation notes, see [README_FIXED.md](README_FIXED.md).

---

## Security & Deployment Notes

- Set a strong, unique `VMC_SECRET_KEY` before using the application beyond local development.
- Keep database credentials in environment variables; never commit passwords or production secrets.
- The current source has a development fallback for the Flask secret key. Always override it with `VMC_SECRET_KEY` in a real deployment.
- The application currently starts with Flask's debug mode enabled in its local run block. Do not expose that development server publicly.
- For production, use a production WSGI server such as Gunicorn behind a properly configured web server and HTTPS.
- Back up the MySQL database regularly and restrict database access to trusted hosts.

Example Gunicorn command (Linux/macOS):

```bash
gunicorn --workers 2 --bind 0.0.0.0:5000 app:app
```

---

## Contributing

Contributions and suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make and test your changes.
4. Open a pull request with a clear description of the changes.

For bugs or feature requests, please use the repository's GitHub Issues section.

---

## License

No license file is currently included in this repository. Unless a license is added, the project should be treated as having no explicit open-source reuse license.

---

**Repository:** [therizlife123-cpu/vmc-app](https://github.com/therizlife123-cpu/vmc-app)
