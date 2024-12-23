from django.shortcuts import render
from django.http import HttpResponse
import os
import subprocess

def dashboard(request):
    # Display list of call recordings
    recordings_path = "/var/spool/asterisk/monitor/"
    recordings = os.listdir(recordings_path) if os.path.exists(recordings_path) else []
    return render(request, "voice_call.html", {"recordings": recordings})

def make_call(request):
    if request.method == "POST":
        number = request.POST.get("number")
        # Execute the Asterisk originate command
        command = f"asterisk -rx 'originate SIP/your-sip-trunk/{number} extension outbound'"
        subprocess.run(command, shell=True)
        return HttpResponse("Call initiated!")
    return HttpResponse("Invalid request.")
