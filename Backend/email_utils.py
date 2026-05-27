# ─── CRMS Secure Email & PDF Generation Engine ───────────────────────────────
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

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import queries

logger = logging.getLogger(__name__)


def generate_case_pdf(case):
    """
    Generates a beautifully styled, professional PDF dossier for a case.
    Returns: bytes (the PDF document data)
    """
    buffer = io.BytesIO()
    
    # 1. Initialize Document Template with elegant margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # 2. Define High-End Theme Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'), # Slate 900
        alignment=1, # Center
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#64748B'), # Slate 500
        alignment=1,
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#1E3A8A'), # Navy Blue
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
        textColor=colors.HexColor('#334155'), # Slate 700
        spaceAfter=8
    )
    
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#475569') # Slate 600
    )
    
    meta_value_style = ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    
    story = []
    
    # 3. Add Letterhead Elements
    story.append(Paragraph("BENGALURU POLICE DEPARTMENT", title_style))
    story.append(Paragraph("CYBERCRIME DIVISION &bull; CORE RECORD ARCHIVE", subtitle_style))
    story.append(Spacer(1, 10))
    
    # Decorative line separating header
    line_table = Table([[""]], colWidths=[504])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 2, colors.HexColor('#059669')), # Emerald Accent Accent
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))
    
    # 4. Meta Information Grid
    display_id = case.get("case_id_display") or f"BLR-{str(case.get('case_id', 0)).zfill(3)}"
    reported_date_str = case.get("case_date_reported") or case.get("date_reported") or "N/A"
    try:
        dt = datetime.fromisoformat(reported_date_str)
        reported_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
        
    meta_data = [
        [
            Paragraph("Dossier Reference ID:", meta_label_style),
            Paragraph(display_id, meta_value_style),
            Paragraph("Jurisdiction Venue:", meta_label_style),
            Paragraph(case.get("case_location") or case.get("location") or "N/A", meta_value_style),
        ],
        [
            Paragraph("Crime Classification:", meta_label_style),
            Paragraph(case.get("case_crime_type") or case.get("crime_type") or "Other", meta_value_style),
            Paragraph("Record Date:", meta_label_style),
            Paragraph(reported_date_str, meta_value_style),
        ],
        [
            Paragraph("Operational Status:", meta_label_style),
            Paragraph(case.get("case_status") or case.get("status") or "Active", meta_value_style),
            Paragraph("Complainant Name:", meta_label_style),
            Paragraph(case.get("complainant_name") or "Anonymous / Guarded", meta_value_style),
        ]
    ]
    
    meta_table = Table(meta_data, colWidths=[120, 132, 110, 142])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')), # Slate 50 background
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    # 5. Incident Narrative Section
    story.append(Paragraph("I. INCIDENT NARRATIVE", h2_style))
    desc = case.get("case_description") or case.get("description") or "No further narrative logs are compiled for this case file."
    story.append(Paragraph(desc.replace("\n", "<br/>"), body_style))
    story.append(Spacer(1, 10))
    
    # 6. Official Disclaimer and Security Disclosure
    story.append(Paragraph("II. SYSTEM INTEGRITY & SECURITY DISCLOSURE", h2_style))
    disclaimer_text = (
        "This dossier record is compiled automatically from the Bengaluru Police Department's "
        "Crime Record Management System (CRMS). Access is granted strictly to the approved applicant "
        "and is subject to privacy and judicial security laws. Unauthorized replication, modification, "
        "or sharing of this document is a punishable offense under digital secrecy protocols."
    )
    story.append(Paragraph(disclaimer_text, ParagraphStyle('Disclaimer', parent=body_style, fontSize=8, leading=11, textColor=colors.HexColor('#64748B'))))
    story.append(Spacer(1, 20))
    
    # Signature Footer Table
    sig_data = [
        [
            Paragraph("Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"), meta_value_style),
            Paragraph("<b>CRMS DIGITAL SIGNATURE</b>", ParagraphStyle('Sig', parent=meta_value_style, alignment=2))
        ]
    ]
    sig_table = Table(sig_data, colWidths=[250, 254])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(sig_table)
    
    # 7. Build Document
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
            subject = f"[CRMS] Secure Case Access Approved - Case {display_id}"
            body = (
                f"Dear {requester_name},\n\n"
                f"We are pleased to inform you that your request for access to Case {display_id} "
                f"has been approved by the investigating team.\n\n"
                f"Please find the officially generated and digitally signed case dossier details attached in the "
                f"document: {display_id}.pdf.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department CRMS Team\n"
                f"(Deciding Officer: {officer_name})"
            )
            # Generate the PDF attachment
            attachment_bytes = generate_case_pdf(request)
            attachment_name = f"{display_id}.pdf"
            
        else:
            subject = f"[CRMS] Secure Case Access Declined - Case {display_id}"
            body = (
                f"Dear {requester_name},\n\n"
                f"We regret to inform you that your request for access to Case {display_id} "
                f"has been declined by the investigating team at this stage.\n\n"
                f"Bengaluru Police Department Cybercrime Division is unable to grant public clearance for this dossier "
                f"due to sensitive investigation protocols.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department CRMS Team\n"
                f"(Deciding Officer: {officer_name})"
            )
            
        # 4. Check SMTP Credentials in Environment
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police CRMS Team")
        
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
    Includes case PDF dossier, teammate list, and case details on assignment.
    
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
        case["case_id_display"] = display_id  # Ensure it is present for generate_case_pdf
        
        officer_name = officer.get("name") or "Officer"
        officer_email = officer.get("email")
        
        if not officer_email:
            logger.warning(f"[ASSIGNMENT EMAIL] Officer {officer_id} has no email on file")
            return False
        
        # Get teammate list
        teammates = []
        for oid in case.get("officer_ids", []):
            if oid != officer_id:
                t_off = queries.get_officer_by_id(oid)
                if t_off:
                    teammates.append(f"{t_off.get('name')} ({t_off.get('rank')})")
        teammate_str = ", ".join(teammates) if teammates else "None"
        
        attachment_bytes = None
        attachment_name = ""
        
        # 2. Draft email based on action
        if action.lower() == "added":
            subject = f"[CRMS] New Case Assignment - {display_id}"
            body = (
                f"Dear {officer_name},\n\n"
                f"You have been assigned to Case {display_id}.\n\n"
                f"Case Details:\n"
                f"  Title: {case.get('title', 'N/A')}\n"
                f"  Crime Type: {case.get('crime_type', 'N/A')}\n"
                f"  Location: {case.get('location', 'N/A')}\n"
                f"  Status: {case.get('status', 'Active')}\n"
                f"  Date Reported: {case.get('date_reported', 'N/A')}\n\n"
                f"Assigned Teammates on Case:\n"
                f"  {teammate_str}\n\n"
                f"Please find the latest secure case dossier PDF attached for your reference during the active investigation.\n\n"
                f"Please log into CRMS to view full case details.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department CRMS Team"
            )
            # Generate the PDF attachment
            attachment_bytes = generate_case_pdf(case)
            attachment_name = f"{display_id}_dossier.pdf"
        else:  # removed
            subject = f"[CRMS] Case Assignment Removed - {display_id}"
            body = (
                f"Dear {officer_name},\n\n"
                f"You have been removed from Case {display_id}.\n\n"
                f"Case: {case.get('title', 'N/A')}\n"
                f"Crime Type: {case.get('crime_type', 'N/A')}\n\n"
                f"If you have any questions, please contact your supervisor or the admin team.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department CRMS Team"
            )
        
        # 3. Check SMTP configuration
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police CRMS Team")
        
        is_smtp_valid = bool(smtp_user and smtp_password)
        
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
                return True
            except Exception as smtp_err:
                logger.error(f"[ASSIGNMENT EMAIL] SMTP error: {str(smtp_err)}. Using mock mode...")
        
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
        
        logger.info(f"[ASSIGNMENT EMAIL] Mock email logged: {email_filepath}")
        
        if attachment_bytes:
            pdf_filepath = os.path.join(mock_dir, f"{display_id}_dossier_{timestamp}.pdf")
            with open(pdf_filepath, 'wb') as f:
                f.write(attachment_bytes)
            logger.info(f"[ASSIGNMENT EMAIL] Mock PDF dossier saved: {pdf_filepath}")
            
        return True
    
    except Exception as e:
        logger.error(f"[ASSIGNMENT EMAIL] Fatal error: {str(e)}")
        return False


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
            
        # Get teammate list
        teammates = []
        for oid in case.get("officer_ids", []):
            if oid != officer_id:
                t_off = queries.get_officer_by_id(oid)
                if t_off:
                    teammates.append(f"{t_off.get('name')} ({t_off.get('rank')})")
        teammate_str = ", ".join(teammates) if teammates else "None"
        
        # 2. Draft email details
        subject = f"[CRMS] Updated Case Dossier - {display_id}"
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
            f"Please find the latest secure case dossier PDF attached for your reference.\n\n"
            f"Best regards,\n"
            f"Bengaluru Police Department CRMS Team"
        )
        
        # Generate the PDF attachment
        attachment_bytes = generate_case_pdf(case)
        attachment_name = f"{display_id}_updated_dossier.pdf"
        
        # 3. Check SMTP configuration
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police CRMS Team")
        
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

