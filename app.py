from flask import Flask, render_template, request, redirect, session, flash, url_for
import os
import mysql.connector
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = os.getenv("VMC_SECRET_KEY", "vmc_secret_key_change_me")


# ==========================================================
# FILE UPLOAD SETTINGS
# ==========================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "images",
    "signatures"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_SIGNATURE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg"
}


# ==========================================================
# DATABASE
# ==========================================================

DB_PASSWORD = os.getenv(
    "VMC_DB_PASSWORD",
    "Rizwan@123"
)

db = mysql.connector.connect(
    host=os.getenv("VMC_DB_HOST", "localhost"),
    user=os.getenv("VMC_DB_USER", "root"),
    password=DB_PASSWORD,
    database="coaching_center",
)

cursor = db.cursor()


# ==========================================================
# MONTHS
# ==========================================================

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
]

MONTH_ORDER_SQL = ", ".join(
    f"'{m}'" for m in MONTHS
)


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def month_key(year, month):
    return year * 12 + month - 1


def normalize_joining_date(joining_date):

    if isinstance(joining_date, datetime):
        return joining_date.date()

    if isinstance(joining_date, str):
        return datetime.strptime(
            joining_date,
            "%Y-%m-%d"
        ).date()

    return joining_date


def days_in_month(year, month):

    if month == 12:
        next_month = date(
            year + 1,
            1,
            1
        )
    else:
        next_month = date(
            year,
            month + 1,
            1
        )

    return (
        next_month -
        date(year, month, 1)
    ).days


def fee_due_date(joining_date, year, month):

    due_day = min(
        joining_date.day,
        days_in_month(year, month)
    )

    return date(
        year,
        month,
        due_day
    )


def login_required():

    if "teacher_id" not in session:
        return redirect(
            url_for("login")
        )

    return None


def is_admin():

    return session.get("teacher_id") == 1


def student_access_allowed(student_id):

    teacher_id = session.get("teacher_id")

    if not teacher_id:
        return False

    # ------------------------------------------------------
    # ADMIN
    # ------------------------------------------------------

    if teacher_id == 1:

        cursor.execute(
            """
            SELECT id
            FROM students
            WHERE id = %s
            """,
            (student_id,)
        )

    # ------------------------------------------------------
    # NORMAL TEACHER
    # ------------------------------------------------------

    else:

        cursor.execute(
            """
            SELECT id
            FROM students
            WHERE id = %s
              AND teacher_id = %s
            """,
            (
                student_id,
                teacher_id
            )
        )

    return cursor.fetchone() is not None


def parse_amount(value):

    try:

        amount = Decimal(
            str(value).strip()
        )

    except (
        InvalidOperation,
        AttributeError
    ):

        raise ValueError(
            "Invalid payment amount"
        )

    if amount <= 0:

        raise ValueError(
            "Payment amount must be greater than 0"
        )

    return amount.quantize(
        Decimal("0.01")
    )


def signature_extension(filename):

    if not filename or "." not in filename:
        return None

    ext = filename.rsplit(
        ".",
        1
    )[1].lower()

    if ext in ALLOWED_SIGNATURE_EXTENSIONS:
        return ext

    return None


# ==========================================================
# FEE LEDGER
# ==========================================================

def build_fee_ledger(
    student_id,
    monthly_fee,
    joining_date,
    through_date=None
):

    joining_date = normalize_joining_date(
        joining_date
    )

    through_date = (
        through_date
        or datetime.now().date()
    )

    if not joining_date:
        return []

    if joining_date > through_date:
        return []

    fee = Decimal(
        str(monthly_fee or 0)
    ).quantize(
        Decimal("0.01")
    )

    cursor.execute(
        """
        SELECT
            id,
            month,
            year,
            total_fee,
            paid_fee,
            remaining_fee,
            payment_date,
            status,
            teacher_id
        FROM fees
        WHERE student_id = %s
        """,
        (student_id,)
    )

    existing = {}

    for row in cursor.fetchall():

        existing[
            (
                int(row[2]),
                row[1]
            )
        ] = row

    start = month_key(
        joining_date.year,
        joining_date.month
    )

    end = month_key(
        through_date.year,
        through_date.month
    )

    ledger = []

    for key in range(
        start,
        end + 1
    ):

        year = key // 12

        month_no = (
            key % 12
        ) + 1

        month_name = MONTHS[
            month_no - 1
        ]

        due_date = fee_due_date(
            joining_date,
            year,
            month_no
        )

        is_due = (
            due_date <= through_date
        )

        row = existing.get(
            (
                year,
                month_name
            )
        )

        if row:

            total = Decimal(
                str(row[3] or 0)
            )

            paid = Decimal(
                str(row[4] or 0)
            )

            remaining = max(
                Decimal(
                    str(row[5] or 0)
                ),
                Decimal("0.00")
            )

            ledger.append(
                {
                    "id": row[0],
                    "month": month_name,
                    "year": year,
                    "total_fee": total,
                    "paid_fee": paid,
                    "remaining_fee": remaining,
                    "status": row[7],
                    "teacher_id": row[8],
                    "due_date": due_date,
                    "is_due": is_due,
                }
            )

        else:

            ledger.append(
                {
                    "id": None,
                    "month": month_name,
                    "year": year,
                    "total_fee": fee,
                    "paid_fee": Decimal("0.00"),
                    "remaining_fee": fee,
                    "status": "Pending",
                    "teacher_id": None,
                    "due_date": due_date,
                    "is_due": is_due,
                }
            )

    return ledger


def ensure_all_current_fee_records():
    return


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    return redirect(
        url_for("login")
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        cursor.execute(
            """
            SELECT
                id,
                teacher_name,
                username,
                password,
                password_hash,
                signature,
                status
            FROM teachers
            WHERE username = %s
            LIMIT 1
            """,
            (username,)
        )

        teacher = cursor.fetchone()

        if teacher:

            teacher_id = teacher[0]
            teacher_name = teacher[1]
            teacher_username = teacher[2]
            old_password = teacher[3]
            password_hash = teacher[4]
            signature = teacher[5]
            status = teacher[6]

            # --------------------------------------------------
            # INACTIVE TEACHER
            # --------------------------------------------------

            if status != "ACTIVE":

                flash(
                    "Your account is inactive. Please contact admin.",
                    "danger"
                )

                return render_template(
                    "login.html"
                )

            password_valid = False

            # --------------------------------------------------
            # HASHED PASSWORD
            # --------------------------------------------------

            if password_hash:

                try:

                    password_valid = check_password_hash(
                        password_hash,
                        password
                    )

                except ValueError:

                    password_valid = False

            # --------------------------------------------------
            # OLD PASSWORD
            # --------------------------------------------------

            elif (
                old_password
                and password == old_password
            ):

                password_valid = True

                new_hash = generate_password_hash(
                    password
                )

                cursor.execute(
                    """
                    UPDATE teachers
                    SET password_hash = %s
                    WHERE id = %s
                    """,
                    (
                        new_hash,
                        teacher_id
                    )
                )

                db.commit()

            # --------------------------------------------------
            # LOGIN SUCCESS
            # --------------------------------------------------

            if password_valid:

                session.clear()

                session["teacher_id"] = teacher_id
                session["teacher_name"] = teacher_name
                session["teacher_username"] = teacher_username
                session["teacher_signature"] = signature

                return redirect(
                    url_for("dashboard")
                )

        flash(
            "Invalid username or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==========================================================
# STUDENTS
# ==========================================================

@app.route(
    "/students",
    methods=["GET", "POST"]
)
def students():

    guard = login_required()

    if guard:
        return guard

    if request.method == "POST":

        student_name = request.form.get(
            "student_name",
            ""
        ).strip()

        mobile = request.form.get(
            "mobile",
            ""
        ).strip()

        student_class = request.form.get(
            "student_class",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        timing = request.form.get(
            "timing",
            ""
        ).strip()

        monthly_fee = request.form.get(
            "monthly_fee",
            ""
        ).strip()

        joining_date = request.form.get(
            "joining_date",
            ""
        ).strip()

        if not all(
            [
                student_name,
                mobile,
                student_class,
                subject,
                timing,
                monthly_fee,
                joining_date
            ]
        ):

            flash(
                "Please fill all required fields.",
                "danger"
            )

            return render_template(
                "students.html"
            )

        try:

            fee = Decimal(
                monthly_fee
            )

            if fee < 0:
                raise InvalidOperation

        except InvalidOperation:

            flash(
                "Monthly fee must be a valid non-negative number.",
                "danger"
            )

            return render_template(
                "students.html"
            )

        try:

            # IMPORTANT:
            # Student automatically belongs to
            # currently logged-in teacher.

            cursor.execute(
                """
                INSERT INTO students
                (
                    student_name,
                    mobile,
                    student_class,
                    subject,
                    timing,
                    monthly_fee,
                    joining_date,
                    status,
                    teacher_id
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'Active',
                    %s
                )
                """,
                (
                    student_name,
                    mobile,
                    student_class,
                    subject,
                    timing,
                    fee,
                    joining_date,
                    session["teacher_id"]
                )
            )

            db.commit()

            flash(
                "Student saved successfully.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        except mysql.connector.Error as exc:

            db.rollback()

            flash(
                f"Could not save student: {exc}",
                "danger"
            )

    return render_template(
        "students.html"
    )


# ==========================================================
# FEES REDIRECT
# ==========================================================

@app.route("/fees")
def fees():

    guard = login_required()

    if guard:
        return guard

    return redirect(
        url_for("fee_dashboard")
    )


# ==========================================================
# PROFILE
# ==========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    guard = login_required()

    if guard:
        return guard

    teacher_id = session["teacher_id"]

    if request.method == "POST":

        signature = request.files.get(
            "signature"
        )

        ext = signature_extension(
            signature.filename
            if signature
            else ""
        )

        if not signature or not signature.filename:

            flash(
                "Please select a signature image.",
                "danger"
            )

        elif not ext:

            flash(
                "Only PNG, JPG or JPEG signature images are allowed.",
                "danger"
            )

        else:

            filename = secure_filename(
                f"teacher_{teacher_id}.{ext}"
            )

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            signature.save(filepath)

            signature_path = (
                f"images/signatures/{filename}"
            )

            cursor.execute(
                """
                UPDATE teachers
                SET signature = %s
                WHERE id = %s
                """,
                (
                    signature_path,
                    teacher_id
                )
            )

            db.commit()

            session[
                "teacher_signature"
            ] = signature_path

            flash(
                "Signature uploaded successfully.",
                "success"
            )

            return redirect(
                url_for("profile")
            )

    cursor.execute(
        """
        SELECT
            teacher_name,
            username,
            signature
        FROM teachers
        WHERE id = %s
        """,
        (teacher_id,)
    )

    teacher = cursor.fetchone()

    if not teacher:

        session.clear()

        return redirect(
            url_for("login")
        )

    return render_template(
        "profile.html",
        teacher=teacher
    )


# ==========================================================
# DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    guard = login_required()

    if guard:
        return guard

    search = request.args.get(
        "search",
        ""
    ).strip()

    selected_month = (
        request.args.get("month")
        or datetime.now().strftime("%B")
    )

    selected_year_raw = (
        request.args.get("year")
        or str(datetime.now().year)
    )

    if selected_month not in MONTHS:

        selected_month = (
            datetime.now().strftime("%B")
        )

    try:

        selected_year = int(
            selected_year_raw
        )

    except (
        TypeError,
        ValueError
    ):

        selected_year = datetime.now().year

    # ======================================================
    # STUDENTS
    # ======================================================

    if is_admin():

        # MAIN ADMIN
        # Can see EVERY student.

        cursor.execute(
            """
            SELECT
                id,
                student_name,
                mobile,
                student_class,
                subject,
                timing,
                monthly_fee,
                joining_date,
                status,
                teacher_id
            FROM students
            WHERE student_name LIKE %s
            ORDER BY id DESC
            """,
            (
                f"%{search}%",
            )
        )

    else:

        # NORMAL TEACHER
        # Can see ONLY own students.

        cursor.execute(
            """
            SELECT
                id,
                student_name,
                mobile,
                student_class,
                subject,
                timing,
                monthly_fee,
                joining_date,
                status,
                teacher_id
            FROM students
            WHERE student_name LIKE %s
              AND teacher_id = %s
            ORDER BY id DESC
            """,
            (
                f"%{search}%",
                session["teacher_id"]
            )
        )

    students_data = cursor.fetchall()

    students_list = []

    total_expected = Decimal("0.00")
    total_collected = Decimal("0.00")
    total_pending = Decimal("0.00")

    today = datetime.now().date()

    for student in students_data:

        monthly_fee = Decimal(
            str(student[6] or 0)
        )

        joining_date = normalize_joining_date(
            student[7]
        )

        ledger = build_fee_ledger(
            student[0],
            monthly_fee,
            joining_date,
            today
        )

        due_records = [
            r
            for r in ledger
            if r["is_due"]
        ]

        overall_pending = sum(
            (
                r["remaining_fee"]
                for r in due_records
            ),
            Decimal("0.00")
        )

        selected_record = next(
            (
                r
                for r in ledger
                if (
                    r["year"] == selected_year
                    and
                    r["month"] == selected_month
                )
            ),
            None
        )

        selected_due = bool(
            selected_record
            and selected_record["is_due"]
        )

        selected_paid = (
            selected_record["paid_fee"]
            if selected_record
            else Decimal("0.00")
        )

        # ======================================================
# PAYMENT STATUS
# ======================================================

        if overall_pending == Decimal("0.00"):
          payment_state = "PAID"
        else:
          payment_state = "PENDING"

        students_list.append(
            student
            + (
                selected_paid,
                overall_pending,
                payment_state,
                selected_due
            )
        )

        if (
            student[8] == "Active"
            and
            selected_record
            and
            selected_due
        ):

            total_expected += (
                selected_record["total_fee"]
            )

            total_collected += (
                selected_record["paid_fee"]
            )

            total_pending += (
                selected_record["remaining_fee"]
            )

    # ======================================================
    # TOTAL STUDENTS
    # ======================================================

    if is_admin():

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM students
            """
        )

    else:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM students
            WHERE teacher_id = %s
            """,
            (
                session["teacher_id"],
            )
        )

    total_students = cursor.fetchone()[0]

    # ======================================================
    # TOTAL MONTHLY FEES
    # ======================================================

    if is_admin():

        cursor.execute(
            """
            SELECT COALESCE(
                SUM(monthly_fee),
                0
            )
            FROM students
            WHERE status = 'Active'
            """
        )

    else:

        cursor.execute(
            """
            SELECT COALESCE(
                SUM(monthly_fee),
                0
            )
            FROM students
            WHERE status = 'Active'
              AND teacher_id = %s
            """,
            (
                session["teacher_id"],
            )
        )

    total_fees = cursor.fetchone()[0]

    collection_percentage = (
        round(
            float(
                (
                    total_collected /
                    total_expected
                ) * 100
            ),
            1
        )
        if total_expected > 0
        else 0
    )

    collection_percentage = min(
        collection_percentage,
        100
    )

    return render_template(
        "dashboard.html",
        students=students_list,
        total_students=total_students,
        total_fees=total_fees,
        total_collected=total_collected,
        total_pending=total_pending,
        total_expected=total_expected,
        collection_percentage=collection_percentage,
        selected_month=selected_month,
        selected_year=selected_year,
    )


# ==========================================================
# EDIT STUDENT
# ==========================================================

@app.route(
    "/edit/<int:id>",
    methods=["GET", "POST"]
)
def edit_student(id):

    guard = login_required()

    if guard:
        return guard

    teacher_id = session.get(
        "teacher_id"
    )

    if is_admin():

        cursor.execute(
            """
            SELECT *
            FROM students
            WHERE id = %s
            """,
            (id,)
        )

    else:

        cursor.execute(
            """
            SELECT *
            FROM students
            WHERE id = %s
              AND teacher_id = %s
            """,
            (
                id,
                teacher_id
            )
        )

    student = cursor.fetchone()

    if not student:

        flash(
            "You are not allowed to edit this student.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        values = (
            request.form.get(
                "student_name",
                ""
            ).strip(),

            request.form.get(
                "mobile",
                ""
            ).strip(),

            request.form.get(
                "student_class",
                ""
            ).strip(),

            request.form.get(
                "subject",
                ""
            ).strip(),

            request.form.get(
                "timing",
                ""
            ).strip(),

            request.form.get(
                "monthly_fee",
                ""
            ).strip(),

            request.form.get(
                "joining_date",
                ""
            ).strip(),
        )

        if not all(values):

            flash(
                "Please fill all fields.",
                "danger"
            )

            return render_template(
                "edit_student.html",
                student=student
            )

        try:

            fee = Decimal(
                values[5]
            )

            if fee < 0:
                raise InvalidOperation

            if is_admin():

                cursor.execute(
                    """
                    UPDATE students
                    SET
                        student_name = %s,
                        mobile = %s,
                        student_class = %s,
                        subject = %s,
                        timing = %s,
                        monthly_fee = %s,
                        joining_date = %s
                    WHERE id = %s
                    """,
                    (
                        values[0],
                        values[1],
                        values[2],
                        values[3],
                        values[4],
                        fee,
                        values[6],
                        id
                    )
                )

            else:

                cursor.execute(
                    """
                    UPDATE students
                    SET
                        student_name = %s,
                        mobile = %s,
                        student_class = %s,
                        subject = %s,
                        timing = %s,
                        monthly_fee = %s,
                        joining_date = %s
                    WHERE id = %s
                      AND teacher_id = %s
                    """,
                    (
                        values[0],
                        values[1],
                        values[2],
                        values[3],
                        values[4],
                        fee,
                        values[6],
                        id,
                        teacher_id
                    )
                )

            db.commit()

            flash(
                "Student updated successfully.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        except InvalidOperation:

            flash(
                "Monthly fee must be a valid non-negative number.",
                "danger"
            )

        except mysql.connector.Error as exc:

            db.rollback()

            flash(
                f"Could not update student: {exc}",
                "danger"
            )

    return render_template(
        "edit_student.html",
        student=student
    )


# ==========================================================
# DELETE STUDENT
# ==========================================================

@app.route("/delete/<int:id>")
def delete_student(id):

    guard = login_required()

    if guard:
        return guard

    teacher_id = session.get(
        "teacher_id"
    )

    if is_admin():

        cursor.execute(
            """
            SELECT id
            FROM students
            WHERE id = %s
            """,
            (id,)
        )

    else:

        cursor.execute(
            """
            SELECT id
            FROM students
            WHERE id = %s
              AND teacher_id = %s
            """,
            (
                id,
                teacher_id
            )
        )

    student = cursor.fetchone()

    if not student:

        flash(
            "You are not allowed to delete this student.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fees
        WHERE student_id = %s
        """,
        (id,)
    )

    fee_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE student_id = %s
        """,
        (id,)
    )

    payment_count = cursor.fetchone()[0]

    if fee_count or payment_count:

        flash(
            "This student cannot be deleted because "
            "fee/payment records already exist.",
            "warning"
        )

        return redirect(
            url_for("dashboard")
        )

    cursor.execute(
        """
        DELETE FROM students
        WHERE id = %s
        """,
        (id,)
    )

    db.commit()

    flash(
        "Student deleted successfully.",
        "success"
    )

    return redirect(
        url_for("dashboard")
    )


# ==========================================================
# TOGGLE STUDENT STATUS
# ==========================================================

@app.route(
    "/toggle_status/<int:id>"
)
def toggle_status(id):

    guard = login_required()

    if guard:
        return guard

    teacher_id = session.get(
        "teacher_id"
    )

    if is_admin():

        cursor.execute(
            """
            SELECT id, status
            FROM students
            WHERE id = %s
            """,
            (id,)
        )

    else:

        cursor.execute(
            """
            SELECT id, status
            FROM students
            WHERE id = %s
              AND teacher_id = %s
            """,
            (
                id,
                teacher_id
            )
        )

    student = cursor.fetchone()

    if not student:

        flash(
            "You are not allowed to change this student's status.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    new_status = (
        "Inactive"
        if student[1] == "Active"
        else "Active"
    )

    if is_admin():

        cursor.execute(
            """
            UPDATE students
            SET status = %s
            WHERE id = %s
            """,
            (
                new_status,
                id
            )
        )

    else:

        cursor.execute(
            """
            UPDATE students
            SET status = %s
            WHERE id = %s
              AND teacher_id = %s
            """,
            (
                new_status,
                id,
                teacher_id
            )
        )

    db.commit()

    return redirect(
        url_for("dashboard")
    )


# ==========================================================
# PAY FEE
# ==========================================================

@app.route(
    "/pay_fee/<int:id>",
    methods=["GET", "POST"]
)
def pay_fee(id):

    guard = login_required()

    if guard:
        return guard

    if is_admin():

        cursor.execute(
            """
            SELECT
                id,
                student_name,
                monthly_fee,
                joining_date
            FROM students
            WHERE id = %s
            """,
            (id,)
        )

    else:

        cursor.execute(
            """
            SELECT
                id,
                student_name,
                monthly_fee,
                joining_date
            FROM students
            WHERE id = %s
              AND teacher_id = %s
            """,
            (
                id,
                session["teacher_id"]
            )
        )

    student = cursor.fetchone()

    if not student:
        return "Student not found", 404

    (
        student_id,
        student_name,
        monthly_fee_raw,
        joining_date
    ) = student

    monthly_fee = Decimal(
        str(monthly_fee_raw or 0)
    ).quantize(
        Decimal("0.01")
    )

    now = datetime.now()

    current_month = now.strftime(
        "%B"
    )

    current_year = now.year

    teacher_id = session[
        "teacher_id"
    ]

    ledger = build_fee_ledger(
        student_id,
        monthly_fee,
        joining_date,
        now.date()
    )

    current_record = next(
        (
            r
            for r in ledger
            if (
                r["month"] == current_month
                and
                r["year"] == current_year
            )
        ),
        None
    )

    due_records = [
        r
        for r in ledger
        if (
            r["is_due"]
            and
            r["remaining_fee"] > 0
        )
    ]

    previous_records = [
        r
        for r in due_records
        if (
            r["year"] < current_year
            or
            (
                r["year"] == current_year
                and
                MONTHS.index(r["month"])
                <
                MONTHS.index(current_month)
            )
        )
    ]

    previous_pending = sum(
        (
            r["remaining_fee"]
            for r in previous_records
        ),
        Decimal("0.00")
    )

    current_is_due = bool(
        current_record
        and
        current_record["is_due"]
    )

    current_month_paid = (
        current_record["paid_fee"]
        if current_record
        else Decimal("0.00")
    )

    current_month_remaining = (
        current_record["remaining_fee"]
        if (
            current_is_due
            and
            current_record
        )
        else Decimal("0.00")
    )

    total_outstanding = (
        previous_pending
        +
        current_month_remaining
    )

    current_due_date = (
        current_record["due_date"]
        if current_record
        else None
    )

    if request.method == "POST":

        try:

            paid_amount = parse_amount(
                request.form.get(
                    "paid_fee",
                    "0"
                )
            )

            payment_mode = (
                request.form.get(
                    "payment_mode",
                    "Cash"
                ).strip()
                or
                "Cash"
            )

            remarks = (
                request.form.get(
                    "remarks",
                    ""
                ).strip()
                or
                None
            )

            if paid_amount > total_outstanding:

                flash(
                    f"Maximum payable amount is ₹ {total_outstanding}.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "pay_fee",
                        id=id
                    )
                )

            remaining_payment = paid_amount

            payment_date = now.date()

            # --------------------------------------------------
            # OLD FEES FIRST
            # --------------------------------------------------

            for record in previous_records:

                if remaining_payment <= 0:
                    break

                allocation = min(
                    remaining_payment,
                    record["remaining_fee"]
                )

                new_paid = (
                    record["paid_fee"]
                    +
                    allocation
                )

                new_remaining = max(
                    record["remaining_fee"]
                    -
                    allocation,
                    Decimal("0.00")
                )

                new_status = (
                    "Paid"
                    if new_remaining == 0
                    else "Partial"
                )

                if record["id"]:

                    cursor.execute(
                        """
                        UPDATE fees
                        SET
                            paid_fee = %s,
                            remaining_fee = %s,
                            status = %s,
                            payment_date = %s,
                            teacher_id = %s
                        WHERE id = %s
                        """,
                        (
                            new_paid,
                            new_remaining,
                            new_status,
                            payment_date,
                            teacher_id,
                            record["id"]
                        )
                    )

                else:

                    cursor.execute(
                        """
                        INSERT INTO fees
                        (
                            student_id,
                            teacher_id,
                            month,
                            year,
                            total_fee,
                            paid_fee,
                            remaining_fee,
                            payment_date,
                            status
                        )
                        VALUES
                        (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            student_id,
                            teacher_id,
                            record["month"],
                            record["year"],
                            record["total_fee"],
                            new_paid,
                            new_remaining,
                            payment_date,
                            new_status
                        )
                    )

                remaining_payment -= allocation

            # --------------------------------------------------
            # CURRENT MONTH
            # --------------------------------------------------

            if (
                remaining_payment > 0
                and
                current_record
                and
                current_is_due
                and
                current_month_remaining > 0
            ):

                allocation = min(
                    remaining_payment,
                    current_month_remaining
                )

                new_paid = (
                    current_month_paid
                    +
                    allocation
                )

                new_remaining = max(
                    current_month_remaining
                    -
                    allocation,
                    Decimal("0.00")
                )

                new_status = (
                    "Paid"
                    if new_remaining == 0
                    else "Partial"
                )

                if current_record["id"]:

                    cursor.execute(
                        """
                        UPDATE fees
                        SET
                            paid_fee = %s,
                            remaining_fee = %s,
                            status = %s,
                            payment_date = %s,
                            teacher_id = %s
                        WHERE id = %s
                        """,
                        (
                            new_paid,
                            new_remaining,
                            new_status,
                            payment_date,
                            teacher_id,
                            current_record["id"]
                        )
                    )

                else:

                    cursor.execute(
                        """
                        INSERT INTO fees
                        (
                            student_id,
                            teacher_id,
                            month,
                            year,
                            total_fee,
                            paid_fee,
                            remaining_fee,
                            payment_date,
                            status
                        )
                        VALUES
                        (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            student_id,
                            teacher_id,
                            current_month,
                            current_year,
                            monthly_fee,
                            new_paid,
                            new_remaining,
                            payment_date,
                            new_status
                        )
                    )

                remaining_payment -= allocation

            # --------------------------------------------------
            # PAYMENT TRANSACTION
            # --------------------------------------------------

            cursor.execute(
                """
                INSERT INTO payments
                (
                    student_id,
                    amount,
                    payment_month,
                    payment_date,
                    payment_mode,
                    remarks
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    student_id,
                    paid_amount,
                    current_month,
                    payment_date,
                    payment_mode[:20],
                    remarks
                )
            )

            db.commit()

            flash(
                f"Payment of ₹ {paid_amount} recorded successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "payment_history",
                    id=student_id
                )
            )

        except (
            ValueError,
            InvalidOperation
        ) as exc:

            db.rollback()

            flash(
                str(exc),
                "danger"
            )

        except mysql.connector.Error as exc:

            db.rollback()

            flash(
                f"Payment could not be saved: {exc}",
                "danger"
            )

    return render_template(
        "pay_fee.html",
        student=student,
        monthly_fee=monthly_fee,
        already_paid=current_month_paid,
        current_pending=total_outstanding,
        previous_pending=previous_pending,
        current_month=current_month,
        current_year=current_year,
        current_due=current_is_due,
        current_due_date=current_due_date,
    )


# ==========================================================
# PAYMENT HISTORY
# ==========================================================

@app.route(
    "/payment_history/<int:id>"
)
def payment_history(id):

    guard = login_required()

    if guard:
        return guard

    if is_admin():

        cursor.execute(
            """
            SELECT
                id,
                student_name,
                student_class,
                subject,
                monthly_fee
            FROM students
            WHERE id = %s
            """,
            (id,)
        )

    else:

        cursor.execute(
            """
            SELECT
                id,
                student_name,
                student_class,
                subject,
                monthly_fee
            FROM students
            WHERE id = %s
              AND teacher_id = %s
            """,
            (
                id,
                session["teacher_id"]
            )
        )

    student = cursor.fetchone()

    if not student:
        return "Student not found", 404

    cursor.execute(
        """
        SELECT
            id,
            month,
            year,
            total_fee,
            paid_fee,
            remaining_fee,
            payment_date,
            status
        FROM fees
        WHERE student_id = %s
        ORDER BY
            year DESC,
            FIELD(month, %s),
            id DESC
        """,
        (
            id,
            current_month_name()
        )
    )

    payments = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            )
        FROM payments
        WHERE student_id = %s
        """,
        (id,)
    )

    transaction_total = (
        cursor.fetchone()[0]
        or 0
    )

    cursor.execute(
        """
        SELECT
            COALESCE(
                SUM(paid_fee),
                0
            )
        FROM fees
        WHERE student_id = %s
        """,
        (id,)
    )

    fee_total = (
        cursor.fetchone()[0]
        or 0
    )

    total_paid = max(
        Decimal(
            str(transaction_total)
        ),
        Decimal(
            str(fee_total)
        )
    )

    return render_template(
        "payment_history.html",
        student=student,
        payments=payments,
        total_paid=total_paid
    )


def current_month_name():

    return datetime.now().strftime(
        "%B"
    )


# ==========================================================
# RECEIPT
# ==========================================================

@app.route(
    "/receipt/<int:payment_id>"
)
def receipt(payment_id):

    guard = login_required()

    if guard:
        return guard

    if is_admin():

        query = """
            SELECT
                fees.id,
                students.student_name,
                students.student_class,
                students.subject,
                fees.month,
                fees.year,
                fees.total_fee,
                fees.paid_fee,
                fees.remaining_fee,
                fees.payment_date,
                fees.status,
                teachers.teacher_name,
                teachers.signature
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            LEFT JOIN teachers
                ON fees.teacher_id = teachers.id
            WHERE fees.id = %s
        """

        params = (
            payment_id,
        )

    else:

        query = """
            SELECT
                fees.id,
                students.student_name,
                students.student_class,
                students.subject,
                fees.month,
                fees.year,
                fees.total_fee,
                fees.paid_fee,
                fees.remaining_fee,
                fees.payment_date,
                fees.status,
                teachers.teacher_name,
                teachers.signature
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            LEFT JOIN teachers
                ON fees.teacher_id = teachers.id
            WHERE fees.id = %s
              AND students.teacher_id = %s
        """

        params = (
            payment_id,
            session["teacher_id"]
        )

    cursor.execute(
        query,
        params
    )

    payment = cursor.fetchone()

    if not payment:
        return "Payment record not found", 404

    return render_template(
        "receipt.html",
        payment=payment
    )


# ==========================================================
# FEE DASHBOARD
# ==========================================================

@app.route("/fee_dashboard")
def fee_dashboard():

    guard = login_required()

    if guard:
        return guard

    # ======================================================
    # TOTAL COLLECTION
    # IMPORTANT:
    # Normal teacher -> only own students
    # Admin -> all students
    # ======================================================

    if is_admin():

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(amount),
                    0
                )
            FROM payments
            """
        )

    else:

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(payments.amount),
                    0
                )
            FROM payments
            JOIN students
                ON payments.student_id = students.id
            WHERE students.teacher_id = %s
            """,
            (
                session["teacher_id"],
            )
        )

    total_collection = (
        cursor.fetchone()[0]
        or 0
    )

    # ======================================================
    # TOTAL PENDING
    # ======================================================

    total_pending = Decimal(
        "0.00"
    )

    paid_payments = 0
    pending_payments = 0

    if is_admin():

        cursor.execute(
            """
            SELECT
                id,
                monthly_fee,
                joining_date
            FROM students
            WHERE status = 'Active'
            """
        )

    else:

        cursor.execute(
            """
            SELECT
                id,
                monthly_fee,
                joining_date
            FROM students
            WHERE status = 'Active'
              AND teacher_id = %s
            """,
            (
                session["teacher_id"],
            )
        )

    active_students = cursor.fetchall()

    today = datetime.now().date()

    for (
        student_id,
        monthly_fee_raw,
        joining_date
    ) in active_students:

        monthly_fee = Decimal(
            str(
                monthly_fee_raw or 0
            )
        ).quantize(
            Decimal("0.01")
        )

        ledger = build_fee_ledger(
            student_id,
            monthly_fee,
            joining_date,
            today
        )

        for record in ledger:

            if not record["is_due"]:
                continue

            remaining = Decimal(
                str(
                    record["remaining_fee"]
                    or 0
                )
            ).quantize(
                Decimal("0.01")
            )

            if remaining > 0:

                total_pending += remaining

                pending_payments += 1

            else:

                paid_payments += 1

    total_payments = (
        paid_payments
        +
        pending_payments
    )

    # ======================================================
    # THIS MONTH COLLECTION
    # ======================================================

    if is_admin():

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(amount),
                    0
                )
            FROM payments
            WHERE MONTH(payment_date)
                    = MONTH(CURDATE())
              AND YEAR(payment_date)
                    = YEAR(CURDATE())
            """
        )

    else:

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(payments.amount),
                    0
                )
            FROM payments
            JOIN students
                ON payments.student_id = students.id
            WHERE students.teacher_id = %s
              AND MONTH(payments.payment_date)
                    = MONTH(CURDATE())
              AND YEAR(payments.payment_date)
                    = YEAR(CURDATE())
            """,
            (
                session["teacher_id"],
            )
        )

    monthly_collection = (
        cursor.fetchone()[0]
        or 0
    )

    # ======================================================
    # RECENT PAYMENTS
    # IMPORTANT FIX:
    # Normal teacher only own students
    # ======================================================

    if is_admin():

        cursor.execute(
            """
            SELECT
                fees.id,
                students.student_name,
                fees.month,
                fees.year,
                fees.paid_fee,
                fees.remaining_fee,
                fees.payment_date,
                fees.status
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            ORDER BY fees.id DESC
            LIMIT 10
            """
        )

    else:

        cursor.execute(
            """
            SELECT
                fees.id,
                students.student_name,
                fees.month,
                fees.year,
                fees.paid_fee,
                fees.remaining_fee,
                fees.payment_date,
                fees.status
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            WHERE students.teacher_id = %s
            ORDER BY fees.id DESC
            LIMIT 10
            """,
            (
                session["teacher_id"],
            )
        )

    recent_payments = cursor.fetchall()

    return render_template(
        "fee_dashboard.html",
        total_collection=total_collection,
        total_pending=total_pending,
        total_payments=total_payments,
        paid_payments=paid_payments,
        pending_payments=pending_payments,
        monthly_collection=monthly_collection,
        recent_payments=recent_payments,
    )


# ==========================================================
# MONTHLY REPORT
# ==========================================================

@app.route("/monthly_report")
def monthly_report():

    guard = login_required()

    if guard:
        return guard

    # ======================================================
    # MONTHLY DATA
    # ======================================================

    if is_admin():

        cursor.execute(
            f"""
            SELECT
                fees.month,
                fees.year,
                SUM(fees.paid_fee)
                    AS total_collection,
                COUNT(*)
                    AS total_payments
            FROM fees
            GROUP BY
                fees.year,
                fees.month
            ORDER BY
                fees.year DESC,
                FIELD(
                    fees.month,
                    {MONTH_ORDER_SQL}
                ) DESC
            """
        )

    else:

        cursor.execute(
            f"""
            SELECT
                fees.month,
                fees.year,
                SUM(fees.paid_fee)
                    AS total_collection,
                COUNT(*)
                    AS total_payments
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            WHERE students.teacher_id = %s
            GROUP BY
                fees.year,
                fees.month
            ORDER BY
                fees.year DESC,
                FIELD(
                    fees.month,
                    {MONTH_ORDER_SQL}
                ) DESC
            """,
            (
                session["teacher_id"],
            )
        )

    monthly_data = cursor.fetchall()

    # ======================================================
    # REPORT TOTALS
    # ======================================================

    if is_admin():

        # --------------------------------------------------
        # ADMIN = ALL DATA
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(paid_fee),
                    0
                )
            FROM fees
            """
        )

        report_total_collection = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM fees
            """
        )

        report_total_payments = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT COUNT(
                DISTINCT CONCAT(
                    year,
                    '-',
                    month
                )
            )
            FROM fees
            """
        )

        report_total_months = (
            cursor.fetchone()[0]
        )

    else:

        # --------------------------------------------------
        # NORMAL TEACHER = ONLY OWN DATA
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(fees.paid_fee),
                    0
                )
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            WHERE students.teacher_id = %s
            """,
            (
                session["teacher_id"],
            )
        )

        report_total_collection = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            WHERE students.teacher_id = %s
            """,
            (
                session["teacher_id"],
            )
        )

        report_total_payments = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT COUNT(
                DISTINCT CONCAT(
                    fees.year,
                    '-',
                    fees.month
                )
            )
            FROM fees
            JOIN students
                ON fees.student_id = students.id
            WHERE students.teacher_id = %s
            """,
            (
                session["teacher_id"],
            )
        )

        report_total_months = (
            cursor.fetchone()[0]
        )

    # ======================================================
    # CHART
    # ======================================================

    chart_labels = [
        f"{row[0]} {row[1]}"
        for row in monthly_data
    ]

    chart_values = [
        float(row[2] or 0)
        for row in monthly_data
    ]

    return render_template(
        "monthly_report.html",
        monthly_data=monthly_data,
        report_total_collection=report_total_collection,
        report_total_payments=report_total_payments,
        report_total_months=report_total_months,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


# ==========================================================
# ADMIN REQUIRED
# ==========================================================

def admin_required():

    guard = login_required()

    if guard:
        return guard

    teacher_id = session.get(
        "teacher_id"
    )

    cursor.execute(
        """
        SELECT status
        FROM teachers
        WHERE id = %s
        """,
        (teacher_id,)
    )

    teacher = cursor.fetchone()

    if not teacher:

        session.clear()

        return redirect(
            url_for("login")
        )

    # ------------------------------------------------------
    # ONLY TEACHER ID 1 = ADMIN
    # ------------------------------------------------------

    if teacher_id != 1:

        flash(
            "Admin access required.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    return None


# ==========================================================
# TEACHER MANAGEMENT
# ==========================================================

@app.route("/teachers")
def teacher_management():

    guard = admin_required()

    if guard:
        return guard

    cursor.execute(
        """
        SELECT
            id,
            teacher_name,
            username,
            signature,
            status
        FROM teachers
        ORDER BY id ASC
        """
    )

    teachers_data = cursor.fetchall()

    return render_template(
        "teachers.html",
        teachers=teachers_data
    )


# ==========================================================
# ADD TEACHER
# ==========================================================

@app.route(
    "/teachers/add",
    methods=["GET", "POST"]
)
def add_teacher():

    guard = admin_required()

    if guard:
        return guard

    if request.method == "POST":

        teacher_name = request.form.get(
            "teacher_name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if (
            not teacher_name
            or
            not username
            or
            not password
        ):

            flash(
                "Teacher name, username and password are required.",
                "danger"
            )

            return render_template(
                "add_teacher.html"
            )

        if len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "danger"
            )

            return render_template(
                "add_teacher.html"
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return render_template(
                "add_teacher.html"
            )

        cursor.execute(
            """
            SELECT id
            FROM teachers
            WHERE username = %s
            LIMIT 1
            """,
            (username,)
        )

        existing = cursor.fetchone()

        if existing:

            flash(
                "This username already exists.",
                "danger"
            )

            return render_template(
                "add_teacher.html"
            )

        password_hash = generate_password_hash(
            password
        )

        try:

            cursor.execute(
                """
                INSERT INTO teachers
                (
                    teacher_name,
                    username,
                    password_hash,
                    status
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    'ACTIVE'
                )
                """,
                (
                    teacher_name,
                    username,
                    password_hash
                )
            )

            db.commit()

            flash(
                "Teacher added successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "teacher_management"
                )
            )

        except mysql.connector.Error as exc:

            db.rollback()

            flash(
                f"Could not add teacher: {exc}",
                "danger"
            )

    return render_template(
        "add_teacher.html"
    )


# ==========================================================
# EDIT TEACHER
# ==========================================================

@app.route(
    "/teachers/edit/<int:id>",
    methods=["GET", "POST"]
)
def edit_teacher(id):

    guard = admin_required()

    if guard:
        return guard

    cursor.execute(
        """
        SELECT
            id,
            teacher_name,
            username,
            status
        FROM teachers
        WHERE id = %s
        """,
        (id,)
    )

    teacher = cursor.fetchone()

    if not teacher:
        return "Teacher not found", 404

    if request.method == "POST":

        teacher_name = request.form.get(
            "teacher_name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        new_password = request.form.get(
            "password",
            ""
        )

        if (
            not teacher_name
            or
            not username
        ):

            flash(
                "Teacher name and username are required.",
                "danger"
            )

            return render_template(
                "edit_teacher.html",
                teacher=teacher
            )

        cursor.execute(
            """
            SELECT id
            FROM teachers
            WHERE username = %s
              AND id != %s
            LIMIT 1
            """,
            (
                username,
                id
            )
        )

        existing = cursor.fetchone()

        if existing:

            flash(
                "This username is already used by another teacher.",
                "danger"
            )

            return render_template(
                "edit_teacher.html",
                teacher=teacher
            )

        try:

            cursor.execute(
                """
                UPDATE teachers
                SET
                    teacher_name = %s,
                    username = %s
                WHERE id = %s
                """,
                (
                    teacher_name,
                    username,
                    id
                )
            )

            if new_password:

                if len(new_password) < 6:

                    flash(
                        "Password must be at least 6 characters.",
                        "danger"
                    )

                    return render_template(
                        "edit_teacher.html",
                        teacher=teacher
                    )

                password_hash = generate_password_hash(
                    new_password
                )

                cursor.execute(
                    """
                    UPDATE teachers
                    SET password_hash = %s
                    WHERE id = %s
                    """,
                    (
                        password_hash,
                        id
                    )
                )

            db.commit()

            flash(
                "Teacher updated successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "teacher_management"
                )
            )

        except mysql.connector.Error as exc:

            db.rollback()

            flash(
                f"Could not update teacher: {exc}",
                "danger"
            )

    return render_template(
        "edit_teacher.html",
        teacher=teacher
    )


# ==========================================================
# TOGGLE TEACHER
# ==========================================================

@app.route(
    "/teachers/toggle/<int:id>"
)
def toggle_teacher(id):

    guard = admin_required()

    if guard:
        return guard

    # ------------------------------------------------------
    # NEVER DEACTIVATE ADMIN
    # ------------------------------------------------------

    if id == 1:

        flash(
            "The primary admin account cannot be deactivated.",
            "warning"
        )

        return redirect(
            url_for(
                "teacher_management"
            )
        )

    cursor.execute(
        """
        SELECT status
        FROM teachers
        WHERE id = %s
        """,
        (id,)
    )

    teacher = cursor.fetchone()

    if not teacher:
        return "Teacher not found", 404

    new_status = (
        "INACTIVE"
        if teacher[0] == "ACTIVE"
        else "ACTIVE"
    )

    cursor.execute(
        """
        UPDATE teachers
        SET status = %s
        WHERE id = %s
        """,
        (
            new_status,
            id
        )
    )

    db.commit()

    flash(
        f"Teacher account {new_status.lower()}.",
        "success"
    )

    return redirect(
        url_for(
            "teacher_management"
        )
    )


# ==========================================================
# DELETE TEACHER
# ==========================================================

@app.route(
    "/teachers/delete/<int:id>"
)
def delete_teacher(id):

    guard = admin_required()

    if guard:
        return guard

    if id == 1:

        flash(
            "The primary admin account cannot be deleted.",
            "warning"
        )

        return redirect(
            url_for(
                "teacher_management"
            )
        )

    cursor.execute(
        """
        SELECT id
        FROM teachers
        WHERE id = %s
        """,
        (id,)
    )

    teacher = cursor.fetchone()

    if not teacher:
        return "Teacher not found", 404

    flash(
        "Teacher accounts are not permanently deleted. "
        "Deactivate the account instead.",
        "warning"
    )

    return redirect(
        url_for(
            "teacher_management"
        )
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )