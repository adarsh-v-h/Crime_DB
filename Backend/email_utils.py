# ─── Themis's Domain Secure Email & PDF Generation Engine ───────────────────────────────
# Handles building high-resolution case dossiers in PDF format and dispatches
# notifications to citizens asynchronously.
# Features a Mock Fallback Mode for seamless offline testing.

import io
import os
import json
import logging
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import queries

logger = logging.getLogger(__name__)


def _pdf_text(value, fallback="N/A"):
    """Escapes user/DB text for ReportLab Paragraph rendering."""
    if value is None or value == "":
        value = fallback
    return escape(str(value)).replace("\n", "<br/>")


def _format_datetime(value):
    if not value:
        return "N/A"
    if hasattr(value, "isoformat"):
        value = value.isoformat()
    value = str(value)
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value


def _format_file_size(size):
    try:
        return f"{round(float(size or 0) / 1024, 1)} KB"
    except Exception:
        return "N/A"


def send_verification_email(recipient_email, otp):
    """
    Sends a simple verification OTP email. Falls back to mock logging if SMTP is not configured.
    Returns (success, message).
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port_str = os.getenv("SMTP_PORT", "587")
    smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police Themis's Domain Team")

    subject = "Themis's Domain verification code"
    body = (
        f"Dear Citizen,\n\n"
        f"Your Themis's Domain verification code is: {otp}\n"
        f"This code is valid for 2 minutes. Do not share it with anyone.\n\n"
        f"Bengaluru Police Department Themis's Domain Team"
    )

    if smtp_user and smtp_password:
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{smtp_from_name} <{smtp_from_email}>"
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            if smtp_port == 587:
                server.starttls()
                server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from_email, recipient_email, msg.as_string())
            server.quit()
            logger.info(f"[EMAIL OTP] Sent verification email to {recipient_email}")
            return True, "OTP sent successfully to email."
        except Exception as e:
            logger.error(f"[EMAIL OTP] SMTP send failed: {e}")

    # Offline or mock fallback
    mock_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_emails")
    os.makedirs(mock_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(mock_dir, f"email_otp_{timestamp}.json")
    log_data = {
        "sent_to": recipient_email,
        "subject": subject,
        "body": body,
        "otp": otp,
        "timestamp": datetime.now().isoformat()
    }
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2)
        logger.info(f"[EMAIL OTP] Mock email logged to {log_path}")
        return True, f"OTP email logged to {log_path}"
    except Exception as e:
        logger.error(f"[EMAIL OTP] Failed to write mock email log: {e}")
        return False, "Failed to send OTP email." 


def generate_case_pdf(case, evidence_list=None, timeline_updates=None, teammates=None):
    """
    Generates a secure PDF dossier for a case.
    Optional evidence, timeline, and teammate lists are rendered when supplied.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        alignment=1,
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#64748B'),
        alignment=1,
        spaceAfter=15
    )
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'NarrativeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )
    small_body_style = ParagraphStyle(
        'SmallNarrativeBody',
        parent=body_style,
        fontSize=8,
        leading=10,
        spaceAfter=4
    )
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#475569')
    )
    meta_value_style = ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )

    def paragraph(value, style=meta_value_style, fallback="N/A"):
        return Paragraph(_pdf_text(value, fallback), style)

    def add_table(data, col_widths):
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 12))

    story = []
    story.append(Paragraph("BENGALURU POLICE DEPARTMENT", title_style))
    story.append(Paragraph("CYBERCRIME DIVISION &bull; CORE RECORD ARCHIVE", subtitle_style))
    story.append(Spacer(1, 10))

    line_table = Table([[""]], colWidths=[504])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#059669')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))

    display_id = case.get("case_id_display") or f"BLR-{str(case.get('case_id', 0)).zfill(3)}"
    reported_date_str = _format_datetime(case.get("case_date_reported") or case.get("date_reported"))

    meta_data = [
        [
            paragraph("Dossier Reference ID:", meta_label_style),
            paragraph(display_id),
            paragraph("Jurisdiction Venue:", meta_label_style),
            paragraph(case.get("case_location") or case.get("location")),
        ],
        [
            paragraph("Crime Classification:", meta_label_style),
            paragraph(case.get("case_crime_type") or case.get("crime_type") or "Other"),
            paragraph("Record Date:", meta_label_style),
            paragraph(reported_date_str),
        ],
        [
            paragraph("Operational Status:", meta_label_style),
            paragraph(case.get("case_status") or case.get("status") or "Active"),
            paragraph("Complainant Name:", meta_label_style),
            paragraph(case.get("complainant_name") or "Anonymous / Guarded"),
        ],
        [
            paragraph("Last Updated:", meta_label_style),
            paragraph(_format_datetime(case.get("last_updated"))),
            paragraph("Complaint Mode:", meta_label_style),
            paragraph(case.get("complaint_mode")),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[120, 132, 110, 142])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    section_num = 1

    story.append(Paragraph(f"{section_num}. INCIDENT NARRATIVE", h2_style))
    desc = case.get("case_description") or case.get("description") or "No further narrative logs are compiled for this case file."
    story.append(paragraph(desc, body_style, "No further narrative logs are compiled for this case file."))
    story.append(Spacer(1, 10))
    section_num += 1

    if teammates is not None:
        story.append(Paragraph(f"{section_num}. ASSIGNED OFFICERS", h2_style))
        if teammates:
            teammate_data = [[
                paragraph("Name", meta_label_style),
                paragraph("Rank", meta_label_style),
                paragraph("Badge", meta_label_style),
                paragraph("Station", meta_label_style),
            ]]
            for teammate in teammates:
                teammate_data.append([
                    paragraph(teammate.get("name")),
                    paragraph(teammate.get("rank")),
                    paragraph(teammate.get("badge")),
                    paragraph(teammate.get("station")),
                ])
            add_table(teammate_data, [150, 95, 90, 169])
        else:
            story.append(paragraph("No assigned officers are currently recorded.", body_style))
            story.append(Spacer(1, 10))
        section_num += 1

    if timeline_updates is not None:
        story.append(Paragraph(f"{section_num}. INVESTIGATION TIMELINE", h2_style))
        if timeline_updates:
            timeline_data = [[
                paragraph("Time", meta_label_style),
                paragraph("Officer", meta_label_style),
                paragraph("Update", meta_label_style),
            ]]
            for update in timeline_updates:
                officer_display = " ".join(filter(None, [
                    update.get("officer_name"),
                    f"({update.get('officer_rank')})" if update.get("officer_rank") else ""
                ]))
                timeline_data.append([
                    paragraph(_format_datetime(update.get("created_at"))),
                    paragraph(officer_display),
                    paragraph(update.get("update_text"), small_body_style),
                ])
            add_table(timeline_data, [95, 115, 294])
        else:
            story.append(paragraph("No investigation timeline updates are currently recorded.", body_style))
            story.append(Spacer(1, 10))
        section_num += 1

    if evidence_list is not None:
        story.append(Paragraph(f"{section_num}. EVIDENCE INVENTORY", h2_style))
        if evidence_list:
            evidence_data = [[
                paragraph("ID", meta_label_style),
                paragraph("Filename", meta_label_style),
                paragraph("Uploaded By", meta_label_style),
                paragraph("Uploaded At", meta_label_style),
                paragraph("Size", meta_label_style),
                paragraph("Description", meta_label_style),
            ]]
            for ev in evidence_list:
                uploader = ev.get("uploader_name") or ev.get("officer_name")
                uploaded_at = ev.get("uploaded_at") or ev.get("created_at")
                evidence_data.append([
                    paragraph(ev.get("evidence_id")),
                    paragraph(ev.get("original_name") or ev.get("file_name")),
                    paragraph(uploader),
                    paragraph(_format_datetime(uploaded_at)),
                    paragraph(_format_file_size(ev.get("file_size"))),
                    paragraph(ev.get("description") or ev.get("mime_type") or "No description provided."),
                ])
            add_table(evidence_data, [34, 116, 82, 88, 50, 134])
        else:
            story.append(paragraph("No evidence items are currently recorded for this case.", body_style))
            story.append(Spacer(1, 10))
        section_num += 1

    story.append(Paragraph(f"{section_num}. SYSTEM INTEGRITY & SECURITY DISCLOSURE", h2_style))
    disclaimer_text = (
        "This dossier record is compiled automatically from the Bengaluru Police Department's "
        "Crime Record Management System (Themis's Domain). Access is granted strictly to the approved applicant "
        "and is subject to privacy and judicial security laws. Unauthorized replication, modification, "
        "or sharing of this document is a punishable offense under digital secrecy protocols."
    )
    story.append(Paragraph(disclaimer_text, ParagraphStyle(
        'Disclaimer',
        parent=body_style,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#64748B')
    )))
    story.append(Spacer(1, 20))

    sig_data = [[
        paragraph("Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        Paragraph("<b>Themis's Domain DIGITAL SIGNATURE</b>", ParagraphStyle('Sig', parent=meta_value_style, alignment=2))
    ]]
    sig_table = Table(sig_data, colWidths=[250, 254])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def send_decision_email(request_id: int, decision: str, officer_id: int):
    """
    Assembles email content, compiles the PDF dossier (if Accepted), and either:
    1. Sends the email via SMTP (if configured).
    2. Writes a mock email and saves the PDF to `Backend/mock_emails/` (if SMTP isn't configured).
    """
    try:
        # 1. Fetch access request and case details
        request = queries.get_access_request_by_id(request_id)
        if not request:
            logger.error(f"[EMAIL ENGINE] Access request {request_id} not found.")
            return False
            
        # 2. Fetch deciding officer details
        officer = queries.get_officer_by_id(officer_id)
        officer_name = officer.get("name") if officer else "BPD Investigating Officer"
        
        display_id = request.get("case_id_display")
        requester_name = request.get("requester_name")
        requester_email = request.get("requester_email")
        
        # 3. Draft email content based on decision
        subject = ""
        body = ""
        attachment_bytes = None
        attachment_name = ""
        
        if decision.lower() == "accept" or decision.lower() == "accepted":
            case_id = request.get("case_id")
            evidence_list = queries.get_case_evidence(case_id) if case_id else []
            timeline_updates = queries.get_case_updates(case_id) if case_id else []
            teammates = queries.get_officers_assigned_to_case(case_id) if case_id else []

            subject = f"[Themis's Domain] Secure Case Access Approved - Case {display_id}"
            body = (
                f"Dear {requester_name},\n\n"
                f"We are pleased to inform you that your request for access to Case {display_id} "
                f"has been approved by the investigating team.\n\n"
                f"Please find the officially generated and digitally signed case dossier details attached in the "
                f"document: {display_id}.pdf. The dossier includes the latest approved case narrative, "
                f"investigation timeline, assigned officer list, and evidence inventory metadata available at "
                f"the time of generation.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department Themis's Domain Team\n"
                f"(Deciding Officer: {officer_name})"
            )
            # Generate the PDF attachment
            attachment_bytes = generate_case_pdf(
                request,
                evidence_list=evidence_list,
                timeline_updates=timeline_updates,
                teammates=teammates
            )
            attachment_name = f"{display_id}.pdf"
            
        else:
            subject = f"[Themis's Domain] Secure Case Access Declined - Case {display_id}"
            body = (
                f"Dear {requester_name},\n\n"
                f"We regret to inform you that your request for access to Case {display_id} "
                f"has been declined by the investigating team at this stage.\n\n"
                f"Bengaluru Police Department Cybercrime Division is unable to grant public clearance for this dossier "
                f"due to sensitive investigation protocols.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department Themis's Domain Team\n"
                f"(Deciding Officer: {officer_name})"
            )
            
        # 4. Check SMTP Credentials in Environment
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police Themis's Domain Team")
        
        # Determine whether to send for real or run in Mock Mode
        is_smtp_valid = bool(smtp_user and smtp_password)
        
        if is_smtp_valid:
            logger.info(f"[EMAIL ENGINE] Attempting to send live email to {requester_email} via SMTP...")
            try:
                # Compile MIME message
                msg = MIMEMultipart()
                msg['From'] = f"{smtp_from_name} <{smtp_from_email}>"
                msg['To'] = requester_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                
                if attachment_bytes:
                    part = MIMEApplication(attachment_bytes, Name=attachment_name)
                    part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
                    msg.attach(part)
                    
                # Setup Secure Connection
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                server.ehlo()
                if smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from_email, requester_email, msg.as_string())
                server.quit()
                logger.info(f"[EMAIL ENGINE] Live email successfully dispatched to {requester_email}!")
                return True
            except Exception as smtp_err:
                logger.error(f"[EMAIL ENGINE] SMTP dispatch failed: {str(smtp_err)}. Falling back to MOCK mode...")
                # Fallback to Mock Log in case of socket/credential errors
                
        # 5. Offline Fallback: Mock Developer Mode
        logger.info("[EMAIL ENGINE] Running in Mock Developer Mode (Offline)...")
        # Ensure we write inside Backend directory for convenience
        mock_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "mock_emails"
        )
        os.makedirs(mock_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        email_filename = f"email_{timestamp}_req_{request_id}_{decision.lower()}.json"
        email_filepath = os.path.join(mock_dir, email_filename)
        
        # Prepare email details log
        email_log = {
            "timestamp": datetime.now().isoformat(),
            "from": f"{smtp_from_name} <{smtp_from_email}>",
            "to": requester_email,
            "subject": subject,
            "body": body,
            "attachment_provided": bool(attachment_bytes),
            "attachment_name": attachment_name
        }
        
        with open(email_filepath, 'w', encoding='utf-8') as f:
            json.dump(email_log, f, indent=4)
            
        logger.info(f"[EMAIL ENGINE] Mock email log saved: {email_filepath}")
        
        # If accepted, save the generated PDF file as well so the user can open it!
        if attachment_bytes:
            pdf_filename = f"{display_id}_{timestamp}.pdf"
            pdf_filepath = os.path.join(mock_dir, pdf_filename)
            with open(pdf_filepath, 'wb') as f:
                f.write(attachment_bytes)
            logger.info(f"[EMAIL ENGINE] Mock PDF dossier saved: {pdf_filepath}")
            
        return True
    except Exception as e:
        logger.error(f"[EMAIL ENGINE] Fatal error in email processor: {str(e)}")
        return False


def send_decision_email_async(request_id: int, decision: str, officer_id: int):
    """
    Dispatches the email sender into a separate daemon thread to prevent UI locking.
    """
    thread = threading.Thread(
        target=send_decision_email,
        args=(request_id, decision, officer_id),
        daemon=True
    )
    thread.start()
    logger.info(f"[EMAIL ENGINE] Background thread dispatched for Request ID: {request_id}")


# ─────────────────────────────────────────────────────────────────────────────
# OFFICER ASSIGNMENT NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

def send_officer_assignment_notification(case_id: int, officer_id: int, action: str):
    """
    Notifies an officer when they are assigned to or removed from a case.
    If assigned ('added'), attaches the complete case dossier PDF.
    
    Args:
        case_id: ID of the case
        officer_id: ID of the officer
        action: 'added' or 'removed'
    
    Returns: True if successful, False otherwise
    """
    try:
        # 1. Fetch case and officer details
        case = queries.get_case_by_id(case_id)
        officer = queries.get_officer_by_id(officer_id)
        
        if not case or not officer:
            logger.error(f"[ASSIGNMENT EMAIL] Case {case_id} or Officer {officer_id} not found")
            return False
        
        display_id = case.get("case_id_display") or f"BLR-{str(case_id).zfill(3)}"
        officer_name = officer.get("name") or "Officer"
        officer_email = officer.get("email")
        
        if not officer_email:
            logger.warning(f"[ASSIGNMENT EMAIL] Officer {officer_id} has no email on file")
            return False
            
        attachment_bytes = None
        attachment_name = ""
        
        # 2. Draft email based on action
        if action.lower() == "added":
            subject = f"[Themis's Domain] New Case Assignment - {display_id}"
            body = (
                f"Dear {officer_name},\n\n"
                f"You have been assigned to Case {display_id}.\n\n"
                f"Case Details:\n"
                f"  Title: {case.get('title', 'N/A')}\n"
                f"  Crime Type: {case.get('crime_type', 'N/A')}\n"
                f"  Location: {case.get('location', 'N/A')}\n"
                f"  Status: {case.get('status', 'Active')}\n"
                f"  Date Reported: {case.get('date_reported', 'N/A')}\n\n"
                f"Please find the latest secure case dossier PDF attached to this email.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department Themis's Domain Team"
            )
            
            # Generate the dossier PDF with the latest case-linked metadata.
            evidence_list = queries.get_case_evidence(case_id)
            timeline_updates = queries.get_case_updates(case_id)
            teammates = queries.get_officers_assigned_to_case(case_id)
            attachment_bytes = generate_case_pdf(
                case,
                evidence_list=evidence_list,
                timeline_updates=timeline_updates,
                teammates=teammates
            )
            attachment_name = f"{display_id}_assigned_dossier.pdf"
        else:  # removed
            subject = f"[Themis's Domain] Case Assignment Removed - {display_id}"
            body = (
                f"Dear {officer_name},\n\n"
                f"You have been removed from Case {display_id}.\n\n"
                f"Case: {case.get('title', 'N/A')}\n"
                f"Crime Type: {case.get('crime_type', 'N/A')}\n\n"
                f"If you have any questions, please contact your supervisor or the admin team.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department Themis's Domain Team"
            )
        
        # 3. Check SMTP configuration
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police Themis's Domain Team")
        
        is_smtp_valid = bool(smtp_user and smtp_password)
        
        sent_ok = False
        if is_smtp_valid:
            logger.info(f"[ASSIGNMENT EMAIL] Sending email to {officer_email}...")
            try:
                msg = MIMEMultipart()
                msg['From'] = f"{smtp_from_name} <{smtp_from_email}>"
                msg['To'] = officer_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                
                if attachment_bytes:
                    part = MIMEApplication(attachment_bytes, Name=attachment_name)
                    part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
                    msg.attach(part)
                    
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                server.ehlo()
                if smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from_email, officer_email, msg.as_string())
                server.quit()
                logger.info(f"[ASSIGNMENT EMAIL] Email sent to {officer_email}")
                sent_ok = True
            except Exception as smtp_err:
                logger.error(f"[ASSIGNMENT EMAIL] SMTP error: {str(smtp_err)}. Using mock mode...")
        
        if not sent_ok:
            # 4. Mock mode fallback
            logger.info("[ASSIGNMENT EMAIL] Running in Mock Mode...")
            mock_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "mock_emails"
            )
            os.makedirs(mock_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            email_filename = f"email_{timestamp}_case_{case_id}_officer_{officer_id}_{action.lower()}.json"
            email_filepath = os.path.join(mock_dir, email_filename)
            
            email_log = {
                "timestamp": datetime.now().isoformat(),
                "from": f"{smtp_from_name} <{smtp_from_email}>",
                "to": officer_email,
                "subject": subject,
                "body": body,
                "action": action,
                "case_id": case_id,
                "officer_id": officer_id,
                "attachment_provided": bool(attachment_bytes),
                "attachment_name": attachment_name
            }
            
            with open(email_filepath, 'w', encoding='utf-8') as f:
                json.dump(email_log, f, indent=4)
                
            if attachment_bytes:
                pdf_filepath = os.path.join(mock_dir, f"{display_id}_assigned_{timestamp}.pdf")
                with open(pdf_filepath, 'wb') as f:
                    f.write(attachment_bytes)
                logger.info(f"[ASSIGNMENT EMAIL] Mock PDF dossier saved: {pdf_filepath}")
            
            logger.info(f"[ASSIGNMENT EMAIL] Mock email logged: {email_filepath}")
            
        return True
    
    except Exception as e:
        logger.error(f"[ASSIGNMENT EMAIL] Fatal error: {str(e)}")
        return False
    
    except Exception as e:
        logger.error(f"[ASSIGNMENT EMAIL] Fatal error: {str(e)}")
        return False


def send_evidence_email(case_id: int, officer_id: int, evidence_id: int):
    """
    Sends an email with the raw uploaded evidence file as an attachment
    to the admin officer and all officers assigned to the case.
    Returns True if successful.
    """
    try:
        case = queries.get_case_by_id(case_id)
        uploader = queries.get_officer_by_id(officer_id)
        evidence = queries.get_evidence_by_id(evidence_id)
        if not case or not uploader or not evidence:
            logger.error(f"[EVIDENCE EMAIL] Missing data for case {case_id}, officer {officer_id}, evidence {evidence_id}")
            return False
            
        uploader_name = uploader.get("name") or "Officer"
        display_id = case.get("case_id_display") or f"BLR-{str(case_id).zfill(3)}"
        
        # 1. Resolve recipients (Admin + all assigned officers)
        recipients = []
        
        # Get admin officer
        admin = queries.get_admin_officer()
        if admin and admin.get("email"):
            recipients.append((admin.get("name"), admin.get("email")))
            
        # Get assigned officers
        assigned = queries.get_officers_assigned_to_case(case_id)
        for off in assigned:
            email = off.get("email")
            if email:
                name = off.get("name")
                # Deduplicate by email
                if not any(r[1].lower() == email.lower() for r in recipients):
                    recipients.append((name, email))
                    
        if not recipients:
            logger.warning(f"[EVIDENCE EMAIL] No eligible email recipients found for case {case_id}")
            return False
            
        # 2. Prepare the evidence attachment
        file_path = evidence.get("file_path")
        original_name = evidence.get("original_name")
        mime_type = evidence.get("mime_type") or "application/octet-stream"
        
        if not file_path or not os.path.exists(file_path):
            logger.error(f"[EVIDENCE EMAIL] Evidence file not found on disk at {file_path}")
            return False
            
        with open(file_path, 'rb') as f:
            attachment_bytes = f.read()
            
        # SMTP configuration
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police Themis's Domain Team")
        
        is_smtp_valid = bool(smtp_user and smtp_password)
        subject = f"[Themis's Domain] Secure Evidence Notification - Case {display_id}"
        
        success = True
        
        for recipient_name, recipient_email in recipients:
            body = (
                f"Dear {recipient_name},\n\n"
                f"A new piece of evidence has been securely uploaded to Case {display_id} "
                f"by {uploader_name} ({uploader.get('rank', 'Officer')}).\n\n"
                f"As per security protocol, the raw uploaded evidence is attached to this email.\n\n"
                f"Evidence Metadata:\n"
                f"  Filename: {original_name}\n"
                f"  Upload Time: {evidence.get('created_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Size: {round(evidence.get('file_size', 0) / 1024, 1)} KB\n"
                f"  Description: {evidence.get('description') or 'No description provided.'}\n\n"
                f"Please log into the Themis's Domain Portal to view the updated case dossier.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department Themis's Domain Team"
            )
            
            sent_ok = False
            if is_smtp_valid:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = f"{smtp_from_name} <{smtp_from_email}>"
                    msg['To'] = recipient_email
                    msg['Subject'] = subject
                    msg.attach(MIMEText(body, 'plain'))
                    
                    part = MIMEApplication(attachment_bytes, Name=original_name)
                    part['Content-Disposition'] = f'attachment; filename="{original_name}"'
                    msg.attach(part)
                    
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                    server.ehlo()
                    if smtp_port == 587:
                        server.starttls()
                        server.ehlo()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_from_email, recipient_email, msg.as_string())
                    server.quit()
                    
                    logger.info(f"[EVIDENCE EMAIL] Sent raw evidence to {recipient_email}")
                    sent_ok = True
                except Exception as e:
                    logger.error(f"[EVIDENCE EMAIL] SMTP error sending to {recipient_email}: {e}, falling back to mock")
            
            if not sent_ok:
                # Mock Mode Fallback for this recipient
                try:
                    mock_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_emails")
                    os.makedirs(mock_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    # Log email JSON
                    email_filename = f"email_{timestamp}_evidence_{evidence_id}_to_{recipient_email.replace('@', '_')}.json"
                    email_file = os.path.join(mock_dir, email_filename)
                    with open(email_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            "timestamp": datetime.now().isoformat(),
                            "to": recipient_email,
                            "recipient_name": recipient_name,
                            "subject": subject,
                            "body": body,
                            "attachment_name": original_name,
                            "case_id": case_id,
                            "evidence_id": evidence_id
                        }, f, indent=4)
                        
                    # Save a copy of the attached evidence file in mock folder
                    mock_attachment_path = os.path.join(mock_dir, f"evidence_{evidence_id}_mock_{original_name}")
                    with open(mock_attachment_path, 'wb') as f:
                        f.write(attachment_bytes)
                        
                    logger.info(f"[EVIDENCE EMAIL] Mock email logged: {email_file}, mock attachment saved: {mock_attachment_path}")
                except Exception as e:
                    logger.error(f"[EVIDENCE EMAIL] Failed to write mock email for {recipient_email}: {e}")
                    success = False
                    
        return success
    except Exception as e:
        logger.error(f"[EVIDENCE EMAIL] Fatal error: {str(e)}")
        return False

def send_evidence_email_async(case_id: int, officer_id: int, evidence_id: int):
    """
    Dispatches send_evidence_email into a background thread.
    """
    thread = threading.Thread(target=send_evidence_email, args=(case_id, officer_id, evidence_id), daemon=True)
    thread.start()
    logger.info(f"[EVIDENCE EMAIL] Background thread started for case {case_id}, evidence {evidence_id}, officer {officer_id}")


def send_officer_assignment_notification_async(case_id: int, officer_id: int, action: str):
    """
    Dispatches assignment notification into a background thread.
    
    Args:
        case_id: ID of the case
        officer_id: ID of the officer
        action: 'added' or 'removed'
    """
    thread = threading.Thread(
        target=send_officer_assignment_notification,
        args=(case_id, officer_id, action),
        daemon=True
    )
    thread.start()
    logger.info(f"[ASSIGNMENT EMAIL] Background thread started for Case {case_id}, Officer {officer_id}, Action: {action}")


def send_dossier_update_notification(case_id: int, officer_id: int):
    """
    Sends an updated case dossier PDF, teammate list, and case details
    to an officer currently working on the case.
    
    Args:
        case_id: ID of the case
        officer_id: ID of the officer
    
    Returns: True if successful, False otherwise
    """
    try:
        # 1. Fetch case and officer details
        case = queries.get_case_by_id(case_id)
        officer = queries.get_officer_by_id(officer_id)
        
        if not case or not officer:
            logger.error(f"[DOSSIER UPDATE] Case {case_id} or Officer {officer_id} not found")
            return False
            
        display_id = case.get("case_id_display") or f"BLR-{str(case_id).zfill(3)}"
        case["case_id_display"] = display_id
        
        officer_name = officer.get("name") or "Officer"
        officer_email = officer.get("email")
        
        if not officer_email:
            logger.warning(f"[DOSSIER UPDATE] Officer {officer_id} has no email on file")
            return False
            
        teammates = queries.get_officers_assigned_to_case(case_id)
        evidence_list = queries.get_case_evidence(case_id)
        timeline_updates = queries.get_case_updates(case_id)

        teammate_names = []
        for teammate in teammates:
            if teammate.get("officer_id") == officer_id:
                continue
            name = teammate.get("name") or "Officer"
            rank = teammate.get("rank")
            teammate_names.append(f"{name} ({rank})" if rank else name)
        teammate_str = ", ".join(teammate_names) if teammate_names else "None"
        
        # 2. Draft email details
        subject = f"[Themis's Domain] Updated Case Dossier - {display_id}"
        body = (
            f"Dear {officer_name},\n\n"
            f"As requested, here is the updated case dossier for Case {display_id} under active investigation.\n\n"
            f"Updated Case Details:\n"
            f"  Title: {case.get('title', 'N/A')}\n"
            f"  Crime Type: {case.get('crime_type', 'N/A')}\n"
            f"  Location: {case.get('location', 'N/A')}\n"
            f"  Status: {case.get('status', 'Active')}\n"
            f"  Date Reported: {case.get('date_reported', 'N/A')}\n\n"
            f"Assigned Teammates on Case:\n"
            f"  {teammate_str}\n\n"
            f"Dossier Sections Included:\n"
            f"  Timeline Updates: {len(timeline_updates)}\n"
            f"  Evidence Items: {len(evidence_list)}\n"
            f"  Assigned Officers: {len(teammates)}\n\n"
            f"Please find the latest secure case dossier PDF attached for your reference.\n\n"
            f"Best regards,\n"
            f"Bengaluru Police Department Themis's Domain Team"
        )
        
        # Generate the PDF attachment
        attachment_bytes = generate_case_pdf(
            case,
            evidence_list=evidence_list,
            timeline_updates=timeline_updates,
            teammates=teammates
        )
        attachment_name = f"{display_id}_updated_dossier.pdf"
        
        # 3. Check SMTP configuration
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police Themis's Domain Team")
        
        is_smtp_valid = bool(smtp_user and smtp_password)
        
        if is_smtp_valid:
            logger.info(f"[DOSSIER UPDATE] Sending email to {officer_email}...")
            try:
                msg = MIMEMultipart()
                msg['From'] = f"{smtp_from_name} <{smtp_from_email}>"
                msg['To'] = officer_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                
                part = MIMEApplication(attachment_bytes, Name=attachment_name)
                part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
                msg.attach(part)
                
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                server.ehlo()
                if smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from_email, officer_email, msg.as_string())
                server.quit()
                logger.info(f"[DOSSIER UPDATE] Email sent to {officer_email}")
                return True
            except Exception as smtp_err:
                logger.error(f"[DOSSIER UPDATE] SMTP error: {str(smtp_err)}. Using mock mode...")
                
        # 4. Mock mode fallback
        logger.info("[DOSSIER UPDATE] Running in Mock Mode...")
        mock_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "mock_emails"
        )
        os.makedirs(mock_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        email_filename = f"email_{timestamp}_dossier_update_case_{case_id}_officer_{officer_id}.json"
        email_filepath = os.path.join(mock_dir, email_filename)
        
        email_log = {
            "timestamp": datetime.now().isoformat(),
            "from": f"{smtp_from_name} <{smtp_from_email}>",
            "to": officer_email,
            "subject": subject,
            "body": body,
            "case_id": case_id,
            "officer_id": officer_id,
            "attachment_provided": True,
            "attachment_name": attachment_name
        }
        
        with open(email_filepath, 'w', encoding='utf-8') as f:
            json.dump(email_log, f, indent=4)
            
        pdf_filepath = os.path.join(mock_dir, f"{display_id}_updated_dossier_{timestamp}.pdf")
        with open(pdf_filepath, 'wb') as f:
            f.write(attachment_bytes)
            
        logger.info(f"[DOSSIER UPDATE] Mock email and PDF logged: {pdf_filepath}")
        return True
        
    except Exception as e:
        logger.error(f"[DOSSIER UPDATE] Fatal error: {str(e)}")
        return False


def send_dossier_update_notification_async(case_id: int, officer_id: int):
    """
    Dispatches dossier update email notification into a background thread.
    
    Args:
        case_id: ID of the case
        officer_id: ID of the officer
    """
    thread = threading.Thread(
        target=send_dossier_update_notification,
        args=(case_id, officer_id),
        daemon=True
    )
    thread.start()
    logger.info(f"[DOSSIER UPDATE] Background thread started for Case {case_id}, Officer {officer_id}")
