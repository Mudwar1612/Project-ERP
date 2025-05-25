from django.contrib import admin
from .models import MenuItem  # Impor model]
from .models import Order, OrderItem, Rating, ServiceRating, Karyawan
from .models import UserProfile
from .models import FoodStock

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "kode_bill", "nama_pemesan", "no_meja", "metode_pembayaran", "total_harga", "tanggal_pesanan")
    inlines = [OrderItemInline]

admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem)

admin.site.register(Rating)
admin.site.register(ServiceRating)



admin.site.register(Karyawan)

admin.site.register(MenuItem)  # Daftarkan model

admin.site.register(UserProfile)

admin.site.register(FoodStock)