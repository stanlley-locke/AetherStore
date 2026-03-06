#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import warnings

# Suppress Reed-Solomon warnings
warnings.filterwarnings('ignore', category=UserWarning, module='reedsolomon')

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aetherstore.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    # Custom pre-command hooks
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        # Auto-run migrations on certain commands
        if command in ['runserver', 'run_node', 'test']:
            from django.core.management import call_command
            try:
                # Check if migrations need to run
                call_command('check', '--deploy', verbosity=0)
            except:
                pass  # Continue even if checks fail
    
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()