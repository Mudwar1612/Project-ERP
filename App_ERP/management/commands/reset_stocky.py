from django.core.management.base import BaseCommand
from django.utils import timezone
from App_ERP.models import MenuItem, FoodStock

class Command(BaseCommand):
    help = "Reset stok ke 50 pcs setiap jam 00.00"

    def handle(self, *args, **kwargs):
        # Ambil waktu saat ini dan konversikan ke waktu lokal Asia/Jakarta
        today = timezone.localtime(timezone.now()).date()
        
        # Loop untuk setiap item menu
        for item in MenuItem.objects.all():
            # Update atau buat stok makanan untuk setiap menu item
            FoodStock.objects.update_or_create(
                menu_item=item,
                date=today,
                defaults={
                    'stock_in': 50,
                    'stock_out': 0,
                    'remaining_stock': 50
                }
            )
            self.stdout.write(f"Stok direset: {item.name} - {today}")