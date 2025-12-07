from django.core.management.base import BaseCommand
from parking.notifications import send_booking_expiry_notifications


class Command(BaseCommand):
    help = "Send booking expiry push notifications to opted-in users."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=30, help="Notify before N minutes to end")

    def handle(self, *args, **options):
        minutes = options["minutes"]
        sent = send_booking_expiry_notifications(minutes)
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} notifications (trigger: {minutes}m before end)"))
