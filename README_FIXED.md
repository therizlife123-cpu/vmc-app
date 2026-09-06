# VMC Fixed Project

This version keeps `coaching_center` as the primary database because its actual schema matches the Flask application. The separate `vidya_mandir_classes` database is not modified.

## Main fixes
- Fixed fee insertion so the unique `(student_id, month, year)` constraint is respected.
- Payment now updates the existing monthly fee row instead of inserting duplicate monthly rows.
- Each payment is also recorded in the existing `payments` table with payment mode and remarks.
- Old pending fees are settled oldest-first, then the current month is paid.
- Added `/logout`.
- Added login protection to all management routes.
- Added flash messages and safer form validation.
- Added student not-found handling.
- Prevented overpayment instead of silently reducing the amount.
- Fixed partial-payment display.
- Fixed monthly report chart to use server-provided data.
- Signature uploads accept PNG/JPG/JPEG safely.

## Database
The app connects to `coaching_center`. Your existing database/data are not changed by this package until you run the app and perform actions.

Set `VMC_DB_PASSWORD` and `VMC_SECRET_KEY` before production use. The current app keeps the old DB password as a fallback only for compatibility.

## V6 fee dashboard behavior

The main dashboard now calculates each student's **total outstanding fee from admission month through the current month**, including months that do not yet have a row in `fees`. The existing selected-month collection summary remains month-specific.

Payment allocation remains oldest-first: a payment is applied to the oldest unpaid month before the current month. Thus ₹500 against ₹1000 August + ₹1000 September leaves August ₹500 pending and September ₹1000 pending; ₹1000 clears August; ₹2000 clears both.
