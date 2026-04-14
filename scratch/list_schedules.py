import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ALUKINTERLAB.settings')
sys.path.append(os.getcwd())
django.setup()

from Assistant.models import AISchedule

schedules = AISchedule.objects.all()
print(f"Total schedules: {len(schedules)}")
for s in schedules:
    print(f"ID: {s.id}, Name: {s.name}, Active: {s.is_active}")
