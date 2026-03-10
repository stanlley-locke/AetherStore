import os
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
import django
django.setup()

from workers.payout_calculator import calculate_payouts

try:
    calculate_payouts()
except Exception as e:
    with open('real_error.txt', 'w') as f:
        f.write(traceback.format_exc())
