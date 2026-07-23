"""
Admin Routes — Extended Features
==================================
Covers:
  • CSV Export          GET  /api/admin/export/csv
  • PDF Report          GET  /api/admin/export/pdf
  • Subject CRUD        GET/POST/DELETE /api/subjects
  • AI Chat             GET  /api/chat
  • WebSocket Monitor   WS   /ws/admin
"""

import csv
import io
import json
import re
import logging
from datetime import timezone, timedelta, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database.connection import get_db
from backend.database.models import User, AttendanceRecord, FraudLog, Subject
from backend.app.auth import get_current_user, require_role

router = APIRouter(tags=["Admin Features"])
logger = logging.getLogger("admin_routes")

IST = timedelta(hours=5, minutes=30)


def _to_ist(dt) -> str:
    if dt is None:
        return ""
    try:
        return dt.replace(tzinfo=timezone.utc).astimezone(timezone(IST)).strftime("%d %b %Y  %I:%M %p")
    except Exception:
        return str(dt)


# ─── WebSocket connection manager ────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active = [c for c in self.active if c != ws]

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


async def notify_new_attendance(record: AttendanceRecord, username: str):
    """Called from attendance route to push real-time updates to admin."""
    await ws_manager.broadcast({
        "type": "new_attendance",
        "id": record.id,
        "username": username,
        "timestamp": _to_ist(record.timestamp),
        "status": record.status,
        "face_verified": record.face_verified,
        "location_verified": record.location_verified,
        "device_verified": record.device_verified,
        "fraud_risk_score": round(record.fraud_risk_score, 1),
    })


# ─── WebSocket endpoint ───────────────────────────────────────────────────────
@router.websocket("/ws/admin")
async def websocket_admin(websocket: WebSocket):
    """Real-time attendance feed for Admin Dashboard."""
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "Live attendance monitor active"})
        while True:
            await websocket.receive_text()  # Keep-alive ping
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ─── CSV Export ───────────────────────────────────────────────────────────────
@router.get("/api/admin/export/csv")
def export_attendance_csv(
    limit: Optional[int] = Query(1000, description="Limit the number of records returned"),
    start_date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    current_user: User = Depends(require_role(["Admin", "Faculty", "Super Admin"])),
    db: Session = Depends(get_db),
):
    """Stream all attendance records as a downloadable CSV file."""
    query = db.query(AttendanceRecord, User.username, User.email).join(User, User.id == AttendanceRecord.user_id)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(AttendanceRecord.timestamp >= start_dt)
        except ValueError:
            pass
            
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(AttendanceRecord.timestamp <= end_dt)
        except ValueError:
            pass

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit or 1000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Username", "Email", "Timestamp (IST)",
        "Status", "Face Verified", "Location Verified",
        "Device Verified", "Risk Score (%)", "Subject"
    ])

    for rec, uname, email in records:
        subject_name = ""
        if rec.details:
            try:
                d = json.loads(rec.details)
                subject_name = d.get("subject", "")
            except Exception:
                pass
        writer.writerow([
            rec.id, uname, email or "",
            _to_ist(rec.timestamp),
            rec.status,
            "Yes" if rec.face_verified else "No",
            "Yes" if rec.location_verified else "No",
            "Yes" if rec.device_verified else "No",
            round(rec.fraud_risk_score, 1),
            subject_name,
        ])

    output.seek(0)
    filename = f"attendance_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─── PDF Report ───────────────────────────────────────────────────────────────
@router.get("/api/admin/export/pdf")
def export_attendance_pdf(
    limit: Optional[int] = Query(1000, description="Limit the number of records returned"),
    start_date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    current_user: User = Depends(require_role(["Admin", "Faculty", "Super Admin"])),
    db: Session = Depends(get_db),
):
    """Generate a formatted PDF attendance report."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="reportlab not installed. Run: pip install reportlab")

    query = db.query(AttendanceRecord, User.username).join(User, User.id == AttendanceRecord.user_id)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(AttendanceRecord.timestamp >= start_dt)
        except ValueError:
            pass
            
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(AttendanceRecord.timestamp <= end_dt)
        except ValueError:
            pass

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit or 1000).all()

    # Total stats
    total = len(records)
    present = sum(1 for r, _ in records if r.status == "Present")
    flagged = sum(1 for r, _ in records if r.status == "Pending Review")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            rightMargin=1*cm, leftMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"],
                                 fontSize=18, textColor=colors.HexColor("#7c3aed"),
                                 alignment=TA_CENTER)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"],
                               fontSize=10, textColor=colors.HexColor("#64748b"),
                               alignment=TA_CENTER)

    elements = [
        Paragraph("AI Attendance System — Report", title_style),
        Spacer(1, 6),
        Paragraph(
            f"Generated: {_to_ist(datetime.utcnow())}  |  "
            f"Total: {total}  |  Present: {present}  |  Flagged: {flagged}",
            sub_style
        ),
        Spacer(1, 14),
    ]

    # Table header
    header = ["#", "Username", "Timestamp (IST)", "Status", "Face", "GPS", "Device", "Risk %"]
    data = [header]
    for i, (rec, uname) in enumerate(records, 1):
        data.append([
            str(i), uname, _to_ist(rec.timestamp), rec.status,
            "✓" if rec.face_verified else "✗",
            "✓" if rec.location_verified else "✗",
            "✓" if rec.device_verified else "✗",
            f"{rec.fraud_risk_score:.0f}%",
        ])

    col_widths = [1*cm, 4*cm, 5*cm, 2.5*cm, 1.5*cm, 1.5*cm, 2*cm, 2*cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        # Colour Present/Flagged in status column
        *[("TEXTCOLOR", (3, i+1), (3, i+1),
           colors.HexColor("#16a34a") if rec.status == "Present" else colors.HexColor("#dc2626"))
          for i, (rec, _) in enumerate(records)],
    ]))
    elements.append(table)
    doc.build(elements)

    buf.seek(0)
    filename = f"attendance_report_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─── Subject CRUD ─────────────────────────────────────────────────────────────
class SubjectCreate(BaseModel):
    name: str
    code: Optional[str] = ""
    faculty: Optional[str] = ""


@router.get("/api/subjects")
def list_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subjects = db.query(Subject).order_by(Subject.name).all()
    return [{"id": s.id, "name": s.name, "code": s.code, "faculty": s.faculty} for s in subjects]


@router.post("/api/subjects")
def create_subject(
    body: SubjectCreate,
    current_user: User = Depends(require_role(["Admin", "Faculty", "Super Admin"])),
    db: Session = Depends(get_db),
):
    subj = Subject(name=body.name.strip(), code=body.code.strip(), faculty=body.faculty.strip())
    db.add(subj)
    db.commit()
    db.refresh(subj)
    return {"id": subj.id, "name": subj.name, "code": subj.code, "faculty": subj.faculty}


@router.delete("/api/subjects/{subject_id}")
def delete_subject(
    subject_id: int,
    current_user: User = Depends(require_role(["Admin", "Super Admin"])),
    db: Session = Depends(get_db),
):
    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subj:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Subject not found")
    db.delete(subj)
    db.commit()
    return {"message": "Subject deleted"}


# ─── AI Chat ─────────────────────────────────────────────────────────────────
@router.get("/api/chat")
def ai_chat(
    q: str = Query(..., description="Natural language question"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simple intent-based chat — answers attendance questions in plain English.
    Works for both students (own data) and admins (all data).
    """
    q_lower = q.lower().strip()
    uid = current_user.id
    is_admin = current_user.role in ("Admin", "Super Admin", "Faculty")

    # ── Intent: attendance rate ──
    if re.search(r"(attendance|rate|percentage|percent|%)", q_lower):
        records = db.query(AttendanceRecord).filter(AttendanceRecord.user_id == uid).all()
        total = len(records)
        present = sum(1 for r in records if r.status == "Present")
        rate = round((present / total) * 100, 1) if total > 0 else 0
        return {
            "answer": f"Your attendance rate is **{rate}%** ({present} present out of {total} total records).",
            "data": {"total": total, "present": present, "rate": rate}
        }

    # ── Intent: flagged / fraud ──
    if re.search(r"(flag|fraud|risk|suspicious|alert|warn)", q_lower):
        if is_admin:
            count = db.query(AttendanceRecord).filter(AttendanceRecord.status == "Pending Review").count()
            return {"answer": f"There are **{count} flagged** attendance records across all students.", "data": {"flagged": count}}
        else:
            records = db.query(AttendanceRecord).filter(
                AttendanceRecord.user_id == uid,
                AttendanceRecord.status == "Pending Review"
            ).all()
            return {
                "answer": f"You have **{len(records)} flagged** attendance records." +
                          (" Your account is clean! ✅" if len(records) == 0 else " Please contact your admin. ⚠️"),
                "data": {"flagged": len(records)}
            }

    # ── Intent: last check-in ──
    if re.search(r"(last|latest|recent|today|when)", q_lower):
        rec = db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == uid
        ).order_by(AttendanceRecord.timestamp.desc()).first()
        if not rec:
            return {"answer": "You haven't marked any attendance yet.", "data": {}}
        return {
            "answer": f"Your last attendance was marked on **{_to_ist(rec.timestamp)}** — Status: **{rec.status}**.",
            "data": {"timestamp": _to_ist(rec.timestamp), "status": rec.status}
        }

    # ── Intent: total count ──
    if re.search(r"(how many|count|total|number)", q_lower):
        if is_admin:
            total = db.query(AttendanceRecord).count()
            students = db.query(User).filter(User.role == "Student").count()
            return {"answer": f"There are **{total} total attendance records** from **{students} students**.", "data": {"total": total, "students": students}}
        else:
            total = db.query(AttendanceRecord).filter(AttendanceRecord.user_id == uid).count()
            return {"answer": f"You have **{total} attendance records** in total.", "data": {"total": total}}

    # ── Intent: subjects ──
    if re.search(r"(subject|class|course|lecture|period)", q_lower):
        subjects = db.query(Subject).all()
        if not subjects:
            return {"answer": "No subjects have been added yet. Ask your admin to add subjects.", "data": {}}
        names = ", ".join(s.name for s in subjects)
        return {"answer": f"Available subjects: **{names}**", "data": {"subjects": [s.name for s in subjects]}}

    # ── Fallback ──
    return {
        "answer": "I can answer questions like:\n"
                  "• *What is my attendance rate?*\n"
                  "• *Was I flagged today?*\n"
                  "• *When was my last check-in?*\n"
                  "• *How many records do I have?*\n"
                  "• *What subjects are available?*",
        "data": {}
    }
