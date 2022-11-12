from app import app, db
from app.models import User, Cat, VetInfo

import sendgrid
import os
from sendgrid.helpers.mail import *

me = User.query.filter_by(FAid='alberto').first()

if me:
    sg = sendgrid.SendGridAPIClient(api_key=app.config['SENDGRID_API_KEY'])
    from_email = Email(app.config['FAWEB_MAILADDR'])
    to_email = To(me.FAname + " <" + me.FAemail + ">")
    subject = "Message de test"
    content = Content("text/plain", "Le compte est bon et operationnel!")
    mail = Mail(from_email, to_email, subject, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    print(response.status_code)
    print(response.body)
    print(response.headers)
