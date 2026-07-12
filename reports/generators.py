"""
reports/generators.py
-----------------------
Builds the actual export files. Kept separate from views.py so the
file-generation logic can be unit-tested independent of HTTP plumbing.

CSV/Excel use pandas (already part of the project's stack per Prompt 1),
which gives one consistent DataFrame -> file API for both formats rather
than hand-rolling csv.writer + openpyxl separately.

PDF uses reportlab's Platypus layer (SimpleDocTemplate + Table + Paragraph)
since it needs actual layout (headings, tables, page breaks) rather than
raw canvas drawing.
"""

import io

import pandas as pd
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _dataframe_to_csv_response(df: pd.DataFrame, filename: str) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    df.to_csv(response, index=False)
    return response


def _dataframe_to_excel_response(df: pd.DataFrame, filename: str, sheet_name: str = "Sheet1") -> HttpResponse:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)

    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------

def machines_dataframe(queryset):
    return pd.DataFrame([
        {
            "Machine Code": m.machine_code,
            "Name": m.name,
            "Type": m.get_machine_type_display(),
            "Department": m.get_department_display(),
            "Location": m.location,
            "Manufacturer": m.manufacturer,
            "Installation Date": m.installation_date,
            "Status": m.get_status_display(),
        }
        for m in queryset
    ])


def export_machines_csv(queryset):
    return _dataframe_to_csv_response(machines_dataframe(queryset), "machines.csv")


def export_machines_excel(queryset):
    return _dataframe_to_excel_response(machines_dataframe(queryset), "machines.xlsx", "Machines")


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

def predictions_dataframe(queryset):
    return pd.DataFrame([
        {
            "Machine": f"{p.machine.machine_code} - {p.machine.name}",
            "Risk Level": p.get_risk_level_display(),
            "Failure Probability": p.failure_probability,
            "Model Version": p.model_version.version_name,
            "Predicted At": p.predicted_at.strftime("%Y-%m-%d %H:%M"),
            "Requested By": str(p.requested_by) if p.requested_by else "",
        }
        for p in queryset
    ])


def export_predictions_csv(queryset):
    return _dataframe_to_csv_response(predictions_dataframe(queryset), "predictions.csv")


def export_predictions_excel(queryset):
    return _dataframe_to_excel_response(predictions_dataframe(queryset), "predictions.xlsx", "Predictions")


# ---------------------------------------------------------------------------
# Maintenance Requests
# ---------------------------------------------------------------------------

def maintenance_dataframe(queryset):
    return pd.DataFrame([
        {
            "Title": r.title,
            "Machine": f"{r.machine.machine_code} - {r.machine.name}",
            "Priority": r.get_priority_display(),
            "Status": r.get_status_display(),
            "Assigned Engineer": str(r.assigned_engineer) if r.assigned_engineer else "Unassigned",
            "Requested By": str(r.requested_by) if r.requested_by else "",
            "Scheduled Date": r.scheduled_date.strftime("%Y-%m-%d %H:%M") if r.scheduled_date else "",
            "Completed At": r.completed_at.strftime("%Y-%m-%d %H:%M") if r.completed_at else "",
            "Created At": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in queryset
    ])


def export_maintenance_csv(queryset):
    return _dataframe_to_csv_response(maintenance_dataframe(queryset), "maintenance_requests.csv")


def export_maintenance_excel(queryset):
    return _dataframe_to_excel_response(maintenance_dataframe(queryset), "maintenance_requests.xlsx", "Maintenance")


# ---------------------------------------------------------------------------
# PDF summary report
# ---------------------------------------------------------------------------

def generate_summary_pdf(stats: dict) -> HttpResponse:
    """
    Builds a one-page plant summary PDF: machine counts, risk distribution,
    and the current top-priority open maintenance requests. `stats` is a
    plain dict assembled by the view (see reports/views.py) from the
    equipment/predictions/maintenance apps.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Smart Predictive Maintenance System", styles["Title"]))
    elements.append(Paragraph("Plant Summary Report", styles["Heading2"]))
    elements.append(Paragraph(f"Generated: {timezone.now():%Y-%m-%d %H:%M}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    # --- Machine overview table ---
    elements.append(Paragraph("Machine Overview", styles["Heading3"]))
    overview_data = [
        ["Total Machines", str(stats["total_machines"])],
        ["Active", str(stats["active_machines"])],
        ["Under Maintenance", str(stats["under_maintenance_machines"])],
    ]
    overview_table = Table(overview_data, colWidths=[8 * cm, 6 * cm])
    overview_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 0.5 * cm))

    # --- Risk distribution table ---
    elements.append(Paragraph("Risk Level Distribution (latest prediction per machine)", styles["Heading3"]))
    risk_data = [["Risk Level", "Machine Count"]] + [
        [level, str(count)] for level, count in stats["risk_counts"].items()
    ]
    risk_table = Table(risk_data, colWidths=[8 * cm, 6 * cm])
    risk_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d3b66")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(risk_table)
    elements.append(Spacer(1, 0.5 * cm))

    # --- Open maintenance requests table ---
    elements.append(Paragraph("Open Maintenance Requests", styles["Heading3"]))
    if stats["open_requests"]:
        req_data = [["Title", "Machine", "Priority", "Status", "Engineer"]] + [
            [r.title, r.machine.machine_code, r.get_priority_display(), r.get_status_display(),
             str(r.assigned_engineer) if r.assigned_engineer else "Unassigned"]
            for r in stats["open_requests"]
        ]
        req_table = Table(req_data, colWidths=[5 * cm, 3 * cm, 2.5 * cm, 3 * cm, 3 * cm])
        req_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d3b66")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elements.append(req_table)
    else:
        elements.append(Paragraph("No open maintenance requests.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="plant_summary_report.pdf"'
    return response
