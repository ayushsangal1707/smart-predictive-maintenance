"""
Parsing + validation for bulk sensor-reading uploads (CSV or Excel).

Expected columns (case-insensitive, extra columns are ignored):
    sensor_name   - must match an existing active SensorDefinition for the
                    chosen machine (case-insensitive)
    value         - numeric
    recorded_at   - optional; parseable datetime string. Blank/missing
                    defaults to "now" at import time.

Design decision: parsing is done with pandas (already part of the project's
tech stack per the Prompt 1 architecture) rather than the csv/openpyxl
modules directly, since pandas gives one consistent DataFrame API for both
CSV and Excel and handles most encoding/type quirks for us.

The parser NEVER raises on bad data rows — it collects a per-row error list
and only imports the rows that validate, so one bad row in a 500-row file
doesn't block the other 499 (this is surfaced to the user as a summary:
"X imported, Y failed" with the specific failed rows listed).
"""

import io

import pandas as pd
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import SensorDefinition, SensorReading, SOURCE_CSV, SOURCE_EXCEL

REQUIRED_COLUMNS = {"sensor_name", "value"}


class UploadParseError(Exception):
    """Raised for file-level problems (can't even start reading rows)."""


def _load_dataframe(uploaded_file, ext):
    """Reads the uploaded file into a DataFrame, or raises UploadParseError."""
    try:
        raw = uploaded_file.read()
        buffer = io.BytesIO(raw)

        if ext == ".csv":
            df = pd.read_csv(buffer)
        else:  # .xlsx / .xls
            df = pd.read_excel(buffer)
    except pd.errors.EmptyDataError:
        raise UploadParseError("The file has no data / no rows.")
    except pd.errors.ParserError:
        raise UploadParseError("The file could not be parsed. Please check it's a valid CSV file.")
    except UnicodeDecodeError:
        raise UploadParseError("The file encoding could not be read. Please save it as UTF-8 CSV.")
    except ValueError as exc:
        # pandas raises plain ValueError for a range of Excel-format issues
        raise UploadParseError(f"The file could not be read as a spreadsheet: {exc}")
    except Exception as exc:  # noqa: BLE001 - last-resort catch, always surfaced to the user
        raise UploadParseError(f"Unexpected error reading the file: {exc}")

    # Normalize column names: strip whitespace, lowercase, so "Sensor Name",
    # " sensor_name", "SENSOR_NAME" all match.
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise UploadParseError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Expected columns: sensor_name, value, recorded_at (optional)."
        )

    if df.empty:
        raise UploadParseError("The file has no data rows.")

    return df


def process_reading_upload(uploaded_file, machine, user):
    """
    Parses `uploaded_file` (CSV or Excel) and creates SensorReading rows for
    the given `machine`.

    Returns a dict:
        {
            "created": int,
            "skipped": int,
            "errors": [ {"row": int, "message": str}, ... ],
        }

    Raises UploadParseError for file-level failures (bad format, missing
    columns, empty file) — the caller should catch this and show it as a
    single top-level error rather than a per-row one.
    """
    ext = "." + uploaded_file.name.rsplit(".", 1)[-1].lower()
    df = _load_dataframe(uploaded_file, ext)

    # Build a case-insensitive lookup of this machine's active sensors so we
    # don't hit the DB once per row.
    sensors_by_name = {
        s.sensor_name.strip().lower(): s
        for s in SensorDefinition.objects.filter(machine=machine, is_active=True)
    }

    if not sensors_by_name:
        raise UploadParseError(
            f"'{machine.name}' has no active sensors defined yet. "
            f"Add at least one sensor definition before uploading readings."
        )

    source_value = SOURCE_CSV if ext == ".csv" else SOURCE_EXCEL

    errors = []
    to_create = []
    now = timezone.now()

    for idx, row in df.iterrows():
        row_num = idx + 2  # +2: pandas is 0-indexed and row 1 is the header

        raw_name = row.get("sensor_name")
        if pd.isna(raw_name) or not str(raw_name).strip():
            errors.append({"row": row_num, "message": "Missing sensor_name."})
            continue

        sensor_key = str(raw_name).strip().lower()
        sensor = sensors_by_name.get(sensor_key)
        if sensor is None:
            errors.append({
                "row": row_num,
                "message": f"Unknown or inactive sensor '{raw_name}' for this machine.",
            })
            continue

        raw_value = row.get("value")
        if pd.isna(raw_value):
            errors.append({"row": row_num, "message": "Missing value."})
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            errors.append({"row": row_num, "message": f"Value '{raw_value}' is not numeric."})
            continue

        recorded_at = now
        raw_recorded_at = row.get("recorded_at") if "recorded_at" in df.columns else None
        if raw_recorded_at is not None and not pd.isna(raw_recorded_at):
            parsed = _parse_timestamp(raw_recorded_at)
            if parsed is None:
                errors.append({
                    "row": row_num,
                    "message": f"Could not parse recorded_at value '{raw_recorded_at}'.",
                })
                continue
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            if parsed > now:
                errors.append({"row": row_num, "message": "recorded_at cannot be in the future."})
                continue
            recorded_at = parsed

        to_create.append(
            SensorReading(
                sensor=sensor,
                value=value,
                recorded_at=recorded_at,
                source=source_value,
                created_by=user,
            )
        )

    created_count = 0
    if to_create:
        SensorReading.objects.bulk_create(to_create)
        created_count = len(to_create)

    return {
        "created": created_count,
        "skipped": len(errors),
        "errors": errors,
    }


def _parse_timestamp(raw_value):
    """Tries Django's ISO parser first, falls back to pandas' flexible parser."""
    text = str(raw_value).strip()
    dt = parse_datetime(text)
    if dt is not None:
        return dt
    try:
        ts = pd.to_datetime(text)
        return ts.to_pydatetime()
    except (ValueError, TypeError):
        return None
