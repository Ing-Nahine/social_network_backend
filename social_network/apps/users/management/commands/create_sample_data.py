"""
Management command to wait for database to be available.
Place this file in: your_app/management/commands/wait_for_db.py
"""
import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Django command to pause execution until database is available"""
    
    help = 'Wait for database to be available'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout in seconds (default: 30)'
        )
        
    def handle(self, *args, **options):
        timeout = options['timeout']
        self.stdout.write(self.style.WARNING('Waiting for database...'))
        
        start_time = time.time()
        db_conn = None
        
        while not db_conn:
            try:
                # Get the default database connection
                db_conn = connections['default']
                # Try to connect
                db_conn.cursor()
                self.stdout.write(
                    self.style.SUCCESS('Database available!')
                )
                break
            except OperationalError:
                elapsed_time = time.time() - start_time
                if elapsed_time >= timeout:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Database unavailable after {timeout} seconds!'
                        )
                    )
                    raise SystemExit(1)
                    
                self.stdout.write(
                    self.style.WARNING(
                        f'Database unavailable, waiting 1 second... '
                        f'({elapsed_time:.1f}s elapsed)'
                    )
                )
                time.sleep(1)