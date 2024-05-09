import smtplib
from email.message import EmailMessage

def send_email_change_notification(email, template_id):

    def setup_server():
        """Set up the SMTP server."""
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        return server

  
    server = setup_server()
    password = "ioqd pldc jjlx dkmm"  # Not recommended to hardcode password
    server.login("noreply@itsolution4india.com", password)

    try:
        body = f"Hello ADMIN,\n\n This is to inform you that a new template has been created with the email: {email}, and template ID: {template_id}.\n\nThank you!"
        subject = "Regarding New Template Creation"

        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = "noreply@itsolution4india.com"
        msg["To"] = "krishna@itsolution4india.com"

        server.send_message(msg)
        server.quit()
        
        return {"message": "Email sent successfully"}
    except Exception as e:
        server.quit()
        return {"error": f"Error sending email: {e}"}
