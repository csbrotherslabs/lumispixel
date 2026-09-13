from django.core.management.base import BaseCommand

from apps.internal_ops.system_monitoring import run_system_monitoring


class Command(BaseCommand):
    help = "Run LumisPixel Internal system monitoring checks and update operational alerts."

    def handle(self, *args, **options):
        results = run_system_monitoring()
        failures = [result for result in results if not result["healthy"]]
        for result in results:
            state = "OK" if result["healthy"] else result["severity"].upper()
            self.stdout.write(f"[{state}] {result['label']}: {result['detail']}")
        self.stdout.write(self.style.SUCCESS(f"Completed {len(results)} checks; {len(failures)} need attention."))
