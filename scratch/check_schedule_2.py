import os
import django

import sys
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ALUKINTERLAB.settings')
django.setup()

from Assistant.models import AISchedule

try:
    obj = AISchedule.objects.get(pk=2)
    print(f"ID: {obj.id}")
    print(f"Name: {obj.name}")
    print(f"First Run At: {obj.first_run_at}")
    print(f"Next Run: {obj.next_run}")
    print(f"Interval Hours: {obj.interval_hours}")
    print(f"Interval Minutes: {obj.interval_minutes}")
    print(f"Is Active: {obj.is_active}")
except Exception as e:
    print(f"Error: {e}")
