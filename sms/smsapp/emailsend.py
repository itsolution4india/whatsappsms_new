import smtplib
import re
from email.message import EmailMessage
from django.core.exceptions import BadRequest

def is_valid_email(email):
    """Verify if the email is valid using regex pattern."""
    regex = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
    return re.search(regex, email) is not None

def setup_server():
    """Set up the SMTP server."""
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    return server

def send_email(email, subject, body, server):

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = "noreply@itsolution4india.com"
    msg["To"] = email

    server.send_message(msg)

def change_email(email, old_mail, server):


    body = f"Hello Sir,\n\nYour email address has been changed from {old_mail} to {email} .\n\nIf you did not request this change, please contact support immediately.\n\nThank you!"
    subject = "Your email address has been updated"
    send_email(email, subject, body, server)

    print("Email updation is successful", email)


def main_send(email,old_mail) :
    if not is_valid_email(email):
        return

    server = setup_server()
    password = "ioqd pldc jjlx dkmm"
    server.login("noreply@itsolution4india.com", password)

    try:
        
        change_email(email, old_mail, server)
    except Exception as e:
        print(f"Error sending email: {e}")
        return

    server.quit()
    return {"message": "sent to your email"}