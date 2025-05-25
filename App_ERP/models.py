from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from django.core.validators import MaxValueValidator
import uuid

class MenuItem(models.Model):
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)

    def __str__(self):
        return self.name
    
def generate_kode_bill():
    return uuid.uuid4().hex[:8].upper()  # 8 karakter unik dari UUID
    
class Order(models.Model):
    kode_bill = models.CharField(max_length=8, unique=True, default=generate_kode_bill)
    nama_pemesan = models.CharField(max_length=100)
    no_meja = models.CharField(max_length=10)
    metode_pembayaran = models.CharField(max_length=20)
    total_harga = models.IntegerField()
    tanggal_pesanan = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Memastikan bahwa tanggal pesanan disimpan dengan zona waktu Jakarta
        if not self.tanggal_pesanan:
            self.tanggal_pesanan = timezone.localtime(timezone.now())  # Konversi waktu ke Jakarta
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nama_pemesan} - Meja {self.no_meja} - {self.tanggal_pesanan}"

class OrderItem(models.Model):
    menu = models.ForeignKey(MenuItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='order_items')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    nama_menu = models.CharField(max_length=100)
    harga = models.IntegerField()
    jumlah = models.IntegerField()

    def __str__(self):
        return f"{self.nama_menu} x {self.jumlah}"

class Rating(models.Model):
    item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='ratings')
    bintang = models.IntegerField()  # nilai dari 1 sampai 5

class ServiceRating(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    bintang = models.IntegerField()

#ADMIN
ROLE_CHOICES = [
    ('superadmin', 'Super Admin'),
    ('inventori', 'Admin Inventori'),
    ('produksi', 'Admin Manajemen Produksi & Stok'),
    ('pos', 'Admin POS'),
    ('keuangan', 'Admin Keuangan'),
    ('crm', 'Admin CRM'),
    ('hrd', 'Admin HRD'),
]

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
        # Opsional, hanya jika memang dibutuhkan:
    email = models.EmailField(blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

JENIS_KELAMIN_CHOICES = [
    ('L', 'Laki-laki'),
    ('P', 'Perempuan'),
]

class Karyawan(models.Model):
    nama_karyawan = models.CharField(max_length=100)
    divisi = models.CharField(max_length=1, choices=[('A', 'Divisi A'), ('B', 'Divisi B'), ('C', 'Divisi C'), ('D', 'Divisi D')], default='A')
    jabatan = models.CharField(max_length=100)
    j_kelamin = models.CharField(max_length=1,choices=JENIS_KELAMIN_CHOICES,default='L')
    alamat = models.CharField(max_length=255, default='Belum diisi')
    kontak = models.CharField(max_length=20, default= 'Belum diisi')
    no_rekening = models.CharField(max_length=50, default='Belum diisi')

    tanggal_masuk = models.DateField(null=False, blank=False, default=date.today) 
    total_kehadiran = models.IntegerField()
    total_izin = models.IntegerField()
    total_alpha = models.IntegerField()
    
    lembur_jam = models.IntegerField(default=0)
    total_gaji = models.PositiveIntegerField(default=0)
    gaji_pokok = models.PositiveIntegerField(default=0)
    tunjangan_jabatan = models.PositiveIntegerField(default=0)
    @property
    def persentase_kehadiran(self):
        total_hari = self.total_kehadiran + self.total_izin + self.total_alpha
        if total_hari > 0:
            return (self.total_kehadiran / total_hari) * 100
        return 0
    
    def masa_kerja_bulan(self):
        if self.tanggal_masuk:
            delta = date.today() - self.tanggal_masuk
            return delta.days // 30
        return 0 # pastikan selalu return integer

    def __str__(self):
        return self.nama_karyawan   

class FoodStock(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    stock_in = models.PositiveIntegerField(default=50)
    stock_out = models.PositiveIntegerField(default=0)
    remaining_stock = models.PositiveIntegerField(default=50)
    status = models.CharField(max_length=100, default='Tersedia')
    
    def save(self, *args, **kwargs):
        # Pastikan tanggal disesuaikan dengan zona waktu Jakarta
        self.date = timezone.localtime(timezone.now()).date()  # Ambil tanggal berdasarkan zona waktu Jakarta
        self.remaining_stock = self.stock_in - self.stock_out
        super().save(*args, **kwargs)

    def _str_(self):
        return f"{self.menu_item.name} - {self.date}"
    
class StokBahanBaku(models.Model):
    kode_bahan_baku = models.CharField(max_length=10, primary_key=True)
    nama_bahan = models.CharField(max_length=100)
    harga_per_unit = models.DecimalField(max_digits=12, decimal_places=0)
    stok_minimum = models.IntegerField(validators=[MaxValueValidator(50)])
    supplier = models.CharField(max_length=100)
    tanggal_kadaluarsa = models.DateField()
    jumlah = models.IntegerField(default=0)
    lokasi = models.CharField(max_length=50, default='Gudang A') 
    tanggal_update = models.DateField(auto_now=True)  

    @property
    def total_harga(self):
        return self.harga_per_unit * self.stok_minimum

    def _str_(self):
        return self.nama_bahan

class TransaksiStok(models.Model):
    bahan = models.ForeignKey(StokBahanBaku, on_delete=models.CASCADE)
    jenis = models.CharField(max_length=10, choices=[('masuk', 'Masuk'), ('keluar', 'Keluar')])
    jumlah = models.IntegerField()
    tanggal = models.DateField()