from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from .forms import ContactForm


def home(request):
    return render(request, "main/home.html")


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            
            email_subject = f"Contact Form: {subject}"
            email_message = f"""
You have received a new message from the contact form:

Name: {name}
Email: {email}
Phone: {phone if phone else 'Not provided'}
Subject: {subject}

Message:
{message}
"""
            
            try:
                send_mail(
                    subject=email_subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.EMAIL_HOST_USER],
                    fail_silently=False,
                )
                messages.success(request, 'Your message has been sent successfully. We will get back to you soon!')
            except Exception as e:
                messages.error(request, 'Sorry, there was an error sending your message. Please try again later.')
                print(f"Email sending error: {e}")
            
            return render(request, "main/contact.html", {'form': ContactForm()})
    else:
        form = ContactForm()
    
    return render(request, "main/contact.html", {'form': form})


def terms(request):
    return render(request, "main/terms.html")


def privacy(request):
    return render(request, "main/privacy.html")
