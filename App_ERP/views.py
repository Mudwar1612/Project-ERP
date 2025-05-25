from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User 
from django.contrib.auth.hashers import make_password 
from django.db.models import Sum, F , Min, Count
from django.utils import timezone 
from django.utils.timezone import localtime
from datetime import timedelta 
from datetime import datetime
from .models import Order, OrderItem, MenuItem, UserProfile, Rating, ServiceRating, ROLE_CHOICES, Karyawan, FoodStock, StokBahanBaku
from django.db import transaction
from .forms import LoginForm, KaryawanForm, AbsensiForm
from django.http import JsonResponse, HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages 
from reportlab.pdfgen import canvas
from io import BytesIO
import json
import uuid
from django.db.models.functions import TruncDate

@csrf_exempt
def simpan_pesanan(request):
    if request.method == "POST":
        data = json.loads(request.body)

        nama_pemesan = data.get("nama_pemesan")
        no_meja = data.get("no_meja")
        metode_pembayaran = data.get("metode_pembayaran")
        pesanan = data.get("pesanan")

        if not nama_pemesan or not no_meja or not pesanan:
            return JsonResponse({"status": "error", "message": "Data tidak lengkap"}, status=400)

        total_harga = sum(int(item["price"]) * int(item["quantity"]) for item in pesanan)
        kode_bill = uuid.uuid4().hex[:8].upper()  # Ambil 8 karakter pertama dari UUID agar lebih pendek

        # Simpan pesanan utama
        order = Order.objects.create(
            kode_bill=kode_bill,
            nama_pemesan=nama_pemesan,
            no_meja=no_meja,
            metode_pembayaran=metode_pembayaran,
            total_harga=total_harga
        )

        # Simpan setiap item pesanan
        for item in pesanan:
            menu_obj = MenuItem.objects.filter(name=item["name"]).first() # aman, tidak error kalau tidak ditemukan. Mencari MenuItem berdasarkan nama dan diambil yang pertama. Kalau tidak ada, hasilnya None, jadi aman

            OrderItem.objects.create(
                order=order,
                menu=menu_obj, # ini relasi Foreignkey ke MenuItem, akan otomatis isi relasi Foreignkey menu
                nama_menu=item["name"],
                harga=item["price"],
                jumlah=item["quantity"]
            )

        return JsonResponse({"status": "success", "message": "Pesanan berhasil disimpan", "redirect_url": f"/sukses/{kode_bill}/"})
    
    return JsonResponse({"status": "error", "message": "Metode tidak diizinkan"}, status=405)

def start(request) :
    return render(request, 'customer/1start.html')

def menu(request):
    today = timezone.localdate()
    menu_items = MenuItem.objects.all()
    data = []

    for item in menu_items:
        # Ambil stok berdasarkan hari ini
        stock = FoodStock.objects.filter(menu_item=item, date=today).first()
        remaining = stock.remaining_stock if stock else 0

        # Kirim nama item dan sisa stok
        data.append({
            'name': item.name,
            'stock': remaining
        })

    return render(request, 'customer/2menu.html', {
        'stock_data_json': json.dumps(data, cls=DjangoJSONEncoder)
    })

#def menu_list(request):
    #items = MenuItem.objects.all()
    #return render(request, 'menu.html', {'items': items})

def payment(request) :
    return render(request, 'customer/3payment.html')

def sukses(request):
    # Ambil pesanan terbaru berdasarkan ID terbesar (pesanan terakhir)
    latest_order = Order.objects.latest('id')  # Ambil pesanan terbaru
    
    # Ambil daftar item yang terkait dengan pesanan tersebut
    order_items = OrderItem.objects.filter(order=latest_order)

    # Mulai transaksi untuk memastikan stok hanya dikurangi jika semuanya berhasil
    try:
        with transaction.atomic():  # Menggunakan transaksi atomik
            for item in order_items:
                # Cari stok berdasarkan menu dan tanggal saat ini
                today = timezone.localtime().date()
                food_stock, created = FoodStock.objects.get_or_create(menu_item=item.menu, date=today)
                
                # Periksa apakah stok cukup
                if food_stock.remaining_stock >= item.jumlah:
                    food_stock.stock_out += item.jumlah  # Tambah stok yang terjual
                    food_stock.save()  # Update sisa stok
                else:
                    raise ValueError(f"Stok tidak cukup untuk item {item.menu.name}")

        # Jika semuanya berhasil, render halaman sukses
        return render(request, 'customer/sukses.html', {
            'order': latest_order,
            'order_items': order_items
        })

    except ValueError as e:
        # Jika stok tidak cukup, tampilkan error
        return render(request, 'customer/error.html', {'error_message': str(e)})

def ratting(request, kode_bill):
    order = get_object_or_404(Order, kode_bill=kode_bill)
    
    if request.method == "POST":
        for item in order.items.all():
            bintang = request.POST.get(f"rating_{item.id}")
            if bintang:
                Rating.objects.create(item=item, bintang=int(bintang))

        service_rate = request.POST.get("service_rating")
        if service_rate:
            ServiceRating.objects.create(order=order, bintang=int(service_rate))

        return redirect('start')  # Ganti dengan halaman sukses

    return render(request, 'customer/ratting.html', {'order': order})

#ADMIN
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)

                # Cek role
                try:
                    profile = user.userprofile
                    role = profile.role

                    if role == 'superadmin':
                        return redirect('superadmin_dashboard')
                    elif role == 'inventori':
                        return redirect('inventori_dashboard')
                    elif role == 'produksi':
                        return redirect('produksi_dashboard')
                    elif role == 'pos':
                        return redirect('pos_dashboard')
                    elif role == 'keuangan':
                        return redirect('keuangan_dashboard')
                    elif role == 'crm':
                        return redirect('crm_dashboard')
                    elif role == 'hrd':
                        return redirect('hrd_dashboard')
                    else:
                        return redirect('unknown_role')
                except UserProfile.DoesNotExist:
                    return redirect('profile_missing')

            else:
                form.add_error(None, "Username atau password salah.")
    else:
        form = LoginForm()

    return render(request, 'loginadm.html', {'form': form})

def superadmin_dashboard(request):
    # Ambil total pengguna
    total_pengguna = UserProfile.objects.count()
    user_profiles = UserProfile.objects.all()  # Ambil semua profil user (untuk mencegah UnboundLocalError)
    # Ambil semua item dengan remaining_stock == 0
    out_of_stock_items = FoodStock.objects.filter(remaining_stock=0)
    # Ambil waktu sekarang berdasarkan timezone Asia/Jakarta
    today = localtime(timezone.now()).date()

    # Filter order yang dibuat hari ini
    pendapatan_hari_ini = Order.objects.filter(
        tanggal_pesanan__date=today
    ).aggregate(total=Sum('total_harga'))['total'] or 0

    # Ambil rentang 7 hari ke belakang dari hari ini
    seven_days_ago = timezone.now() - timedelta(days=7)

    # Filter OrderItem berdasarkan tanggal pesanan dari Order
    produk_terlaris = OrderItem.objects.filter(
        order__tanggal_pesanan__gte=seven_days_ago
    ).values('nama_menu').annotate(
        total_terjual=Sum('jumlah'),
        total_pendapatan=Sum(F('jumlah') * F('harga'))
    ).order_by('-total_terjual')[:5]

    if request.method == 'POST':
        print("Request POST data:", request.POST)

        # Menambahkan User (Super Admin) dan UserProfile
        if 'create_user' in request.POST:
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            role = request.POST.get('role')
            
            # Validasi sederhana
            if username and email and password and role:
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create(
                        username=username,
                        email=email,
                        password=make_password(password)
                    )
                    UserProfile.objects.create(
                        user=user,
                        role=role,
                        email=email,
                        password=user.password  # hanya kalau memang butuh simpan hash di UserProfile
                    )
                    # Feedback berhasil dengan menggunakan messages framework
                    messages.success(request, "User berhasil dibuat!")
                else:
                    messages.error(request, "Username sudah terpakai!")
            else:
                messages.error(request, "Semua kolom harus diisi!")

        # Menghapus User
        if 'delete_selected' in request.POST:
            user_ids = request.POST.getlist('user_ids')
            if user_ids:
                User.objects.filter(id__in=user_ids).delete()
                messages.success(request, f"{len(user_ids)} admin berhasil dihapus.")
            else:
                messages.warning(request, "Tidak ada admin yang dipilih.")
            return redirect('superadmin_dashboard')

        # Menambahkan Karyawan
        elif 'create_karyawan' in request.POST:
            karyawan_form = KaryawanForm(request.POST)
            if karyawan_form.is_valid():
                karyawan_form.save()
                messages.success(request, "Karyawan berhasil ditambahkan!")
                return redirect('superadmin_dashboard')  # Kembali ke dashboard setelah menyimpan data
            else:
                messages.error(request, "Ada kesalahan dalam pengisian form!")

        # Menghapus Karyawan
        # if 'delete_karyawan' in request.POST:
        #     karyawan_ids = request.POST.getlist('karyawan_ids')
        #     if karyawan_ids:
        #         Karyawan.objects.filter(id__in=karyawan_ids).delete()
        #     return redirect('superadmin_dashboard')

    # Ambil data order terbaru
    orders = Order.objects.all().order_by('-tanggal_pesanan')[:3]

    # Hitung total penjualan
    total_penjualan = Order.objects.aggregate(total=Sum('total_harga'))['total'] or 0

    # Form untuk menambah karyawan
    karyawan_form = KaryawanForm()

    # Ambil data stok produk
    food_stock_list = FoodStock.objects.select_related('menu_item').order_by('-date')

    # Hitung rentang waktu untuk chart (7 hari terakhir)
    start_week = today - timedelta(days=today.weekday())  # Senin minggu ini

    chart_labels = []
    chart_data = []

    for i in range(7):
        day = start_week + timedelta(days=i)
        label = day.strftime('%A')  # e.g. 'Monday'
        total = Order.objects.filter(tanggal_pesanan__date=day).aggregate(Sum('total_harga'))['total_harga__sum'] or 0

        chart_labels.append(label)
        chart_data.append(total)

    karyawans = Karyawan.objects.all()

    for k in karyawans:
    # Gaji harian tergantung masa kerja
        gaji_perhari = 80_000 if k.masa_kerja_bulan() < 3 else 100_000

        kehadiran_gaji = k.total_kehadiran * gaji_perhari
        izin_gaji = k.total_izin * (gaji_perhari // 2)
        lembur_gaji = k.lembur_jam * 10_000

    # Tambahan: gaji pokok & tunjangan jabatan
        gaji_pokok = k.gaji_pokok
        tunjangan = k.tunjangan_jabatan

        total = kehadiran_gaji + izin_gaji + lembur_gaji + gaji_pokok + tunjangan

    # Simpan ke database
    if k.total_gaji != total:
        k.total_gaji = total
        k.save()

# Total semua gaji karyawan
    total_gaji_karyawan = Karyawan.objects.aggregate(Sum('total_gaji'))['total_gaji__sum'] or 0
    # for k in karyawans:
    #     # Gaji harian tergantung masa kerja
    #     gaji_perhari = 80_000 if k.masa_kerja_bulan() < 3 else 100_000

    #     kehadiran_gaji = k.total_kehadiran * gaji_perhari
    #     izin_gaji = k.total_izin * (gaji_perhari // 2)
    #     lembur_gaji = k.lembur_jam * 10_000
    #     total = kehadiran_gaji + izin_gaji + lembur_gaji

    #     # Simpan ke database
    #     if k.total_gaji != total:
    #         k.total_gaji = total
    #         k.save()

    # # Total semua gaji karyawan
    # total_gaji_karyawan = Karyawan.objects.aggregate(Sum('total_gaji'))['total_gaji__sum'] or 0

    # Total pengeluaran (dalam contoh ini hanya gaji karyawan)
    total_pengeluaran = total_gaji_karyawan

    # Ambil data stok produk
    food_stock_list = FoodStock.objects.select_related('menu_item').order_by('-date')

    # Filter OrderItem berdasarkan tanggal pesanan dari Order
    produk_terlaris = OrderItem.objects.filter(
        order__tanggal_pesanan__gte=seven_days_ago
    ).values('nama_menu').annotate(
        total_terjual=Sum('jumlah'),
        total_pendapatan=Sum(F('jumlah') * F('harga'))
    ).order_by('-total_terjual')[:5]
    total_gaji_karyawan = Karyawan.objects.aggregate(Sum('total_gaji'))['total_gaji__sum'] or 0
    absensi = Karyawan.objects.aggregate(
        total_hadir=Sum('total_kehadiran'),
        total_izin=Sum('total_izin'),
        total_alpha=Sum('total_alpha')
    )
    return render(request, 'admin/superadm.html', {
        'roles': ROLE_CHOICES,
        'user_profiles': user_profiles,
        'orders': orders,
        'total_penjualan': total_penjualan,
        'karyawan_form': karyawan_form,
        'karyawans': Karyawan.objects.all(),
        'total_pengguna': total_pengguna,
        'pendapatan_hari_ini': pendapatan_hari_ini,
        'out_of_stock_items': out_of_stock_items,
        'produk_terlaris': produk_terlaris,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'karyawans': karyawans,
        'total_gaji_karyawan': total_gaji_karyawan,
        'total_pengeluaran': total_pengeluaran,
        'food_stock_list': food_stock_list,
        'total_hadir': absensi.get('total_hadir') or 0,
        'total_izin': absensi.get('total_izin') or 0,
        'total_alpha': absensi.get('total_alpha') or 0,
    })

def generate_kode_bahan_baku():
    count = StokBahanBaku.objects.count()
    return f"BBK{count + 1:03d}"

def inventori_dashboard(request):
    if request.method == "POST":
        kode = generate_kode_bahan_baku()
        nama = request.POST.get('Bahan')
        stok_min = int(request.POST.get('stok_minimum'))
        print(stok_min)

        if stok_min >= 50:
            messages.error(request, "Stok minimum tidak boleh lebih dari atau sama dengan 50.")
            return redirect('inventori_dashboard')

        supplier = request.POST.get('suplier')
        harga = request.POST.get('harga')
        tanggal_str = request.POST.get('tanggal')  
        jumlah = int(request.POST.get('jumlah') or 0)
        lokasi = request.POST.get('lokasi') or 'Gudang A'
        tanggal_update = timezone.now()

        # Convert string ke date
        try:
            tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            tanggal = timezone.now().date()  # default ke tanggal sekarang
        
        # Membuat data stok baru
        StokBahanBaku.objects.create(
            kode_bahan_baku=kode,
            nama_bahan=nama,
            stok_minimum=stok_min,
            supplier=supplier,
            harga_per_unit=harga,
            tanggal_kadaluarsa=tanggal,
            jumlah=jumlah,
            lokasi=lokasi,
            tanggal_update=tanggal_update
        )

        # Menampilkan pesan sukses setelah data berhasil disimpan
        messages.success(request, "Data bahan baku berhasil ditambahkan.")

        # Menghitung total stok setelah penambahan
        total_stok = StokBahanBaku.objects.aggregate(total=Sum('stok_minimum'))['total']
        if total_stok is None:
            total_stok = 0
        
        messages.success(request, f"Total stok saat ini adalah {total_stok} unit.")

        return redirect('inventori_dashboard')
    
    # Ambil semua data stok yang ada di database
    data_stok = StokBahanBaku.objects.all().order_by('nama_bahan')
    
    # Hitung data dashboard
    total_item = data_stok.count()
    total_stok = data_stok.aggregate(total=Sum('stok_minimum'))['total'] or 0
    total_stok_per_bahan = data_stok.aggregate(total=Sum('nama_bahan'))['total'] or 0
    stok_kritis = data_stok.filter(jumlah__lte=F('stok_minimum')).count()
    stok_kosong = data_stok.filter(jumlah=0).count()
    
    context = {
        'data_stok': data_stok,
        'total_item': total_item,
        'total_stok': total_stok,
        'stok_kritis': stok_kritis,
        'stok_kosong': stok_kosong,
    }
    
    return render(request, 'admin/inventoriadm.html', context)

def produksi_dashboard(request):
    # Ambil semua item dengan remaining_stock == 0
    out_of_stock_items = FoodStock.objects.filter(remaining_stock=0)

    # Ambil waktu sekarang berdasarkan timezone Asia/Jakarta
    today = localtime(timezone.now()).date()

    TARGET_PER_HARI = 1150

    # Ambil semua tanggal unik dari OrderItem, urut dari terbaru
    unique_dates = OrderItem.objects.values_list('order__tanggal_pesanan__date', flat=True).distinct().order_by('-order__tanggal_pesanan__date')

    report_data = []

    for tanggal in unique_dates:
        # Hitung jumlah terbeli berdasarkan OrderItem
        jumlah_terbeli = OrderItem.objects.filter(
            order__tanggal_pesanan__date=tanggal
        ).aggregate(total=Sum('jumlah'))['total'] or 0

        print(f"{tanggal} => total terbeli: {jumlah_terbeli}")

        # Hitung sisa target
        sisa_target = max(TARGET_PER_HARI - jumlah_terbeli, 0)

        # Cari semua OrderItem untuk hari itu
        order_items_hari_ini = OrderItem.objects.filter(order__tanggal_pesanan__date=tanggal)

        # Hitung jumlah rating bintang <= 2
        rating_reject = Rating.objects.filter(
            item__in=order_items_hari_ini,
            bintang__lte=2
        ).count()

        report_data.append({
            'tanggal': tanggal,
            'jumlah_terbeli': jumlah_terbeli,
            'target_produksi': sisa_target,
            'cacat': rating_reject,
        })

    # Ambil data stok produk
    food_stock_list = FoodStock.objects.select_related('menu_item').order_by('-date')

    # Cek dan update status tiap item berdasarkan remaining_stock
    for item in food_stock_list:
        if item.remaining_stock == 0:
            if item.status != 'Habis':
                item.status = 'Habis'
                item.save()
        else:
            if item.status != 'Tersedia':
                item.status = 'Tersedia'
                item.save()

    # Filter order yang dibuat hari ini dan hitung total pendapatan
    pendapatan_hari_ini = Order.objects.filter(
        tanggal_pesanan__date=today
    ).aggregate(total=Sum('total_harga'))['total'] or 0

    # Ambil data order terbaru dengan prefetch related untuk order items
    orders = Order.objects.prefetch_related('items').all().order_by('-tanggal_pesanan')[:3]

    # --- Tambahan: ambil data rating lengkap dengan menu item terkait ---
    rating_list = []
    for rating in Rating.objects.select_related('item__menu').all():
        rating_list.append({
            'nama_produk': rating.item.menu.name if rating.item.menu else rating.item.nama_menu,
            'bintang': rating.bintang,
        })

    total_terjual=Sum('jumlah'),
    data_stok = StokBahanBaku.objects.all().order_by('nama_bahan')
    context = {'data_stok': data_stok}

    return render(request, 'admin/produksiadm.html', {
        'out_of_stock_items': out_of_stock_items,
        'food_stock_list': food_stock_list,
        'pendapatan_hari_ini': pendapatan_hari_ini,
        'orders': orders,
        'rating_list': rating_list,
        'jumlah' :  total_terjual,
        'report_data' : report_data,
        'data_stok': data_stok,
    })


# def keuangan_dashboard(request) :
#     return render(request, 'admin/keuanganadm.html')
def keuangan_dashboard(request):
    # Total Pengguna Aktif
    total_pengguna = UserProfile.objects.count()

    # Pendapatan Hari Ini
    today = localtime(timezone.now()).date()
    seven_days_ago = today - timedelta(days=7)  # 7 hari terakhir termasuk hari ini
    pendapatan_hari_ini = Order.objects.filter(tanggal_pesanan__date=today).aggregate(total=Sum('total_harga'))['total'] or 0
        # 2. Total transaksi hari ini
    total_transaksi = Order.objects.filter(
        tanggal_pesanan__date=today
    ).count()

    pendapatan_mingguan_qs = (
        Order.objects
        .filter(tanggal_pesanan__gte=seven_days_ago)
        .annotate(hari=TruncDate('tanggal_pesanan'))
        .values('hari')
        .annotate(total=Sum('total_harga'))
        .order_by('hari')
    )
    
    produk_terlaris = (
        OrderItem.objects
        .filter(order__tanggal_pesanan__gte=seven_days_ago)
        .values('nama_menu')
        .annotate(jumlah_terjual=Sum('jumlah'), total_pendapatan=Sum('harga'))
        .order_by('-jumlah_terjual')[:5]
    )
        # Data penjualan hari ini
    penjualan_harian_qs = (
        OrderItem.objects
        .select_related('order')
        .filter(order__tanggal_pesanan__date=today)
        .order_by('order__tanggal_pesanan')
    )

    # Buat list label & data untuk Chart.js
    labels = [item['hari'].strftime("%d %b") for item in pendapatan_mingguan_qs]
    data = [item['total'] for item in pendapatan_mingguan_qs]
    # Karyawan Hadir
    karyawan_hadir = Karyawan.objects.filter(total_kehadiran__gt=0).count()
    total_karyawan = Karyawan.objects.count()

    # Hitung rentang waktu untuk chart (7 hari terakhir)
    start_week = today - timedelta(days=today.weekday())  # Senin minggu ini

    for i in range(7):
        day = start_week + timedelta(days=i)
        label = day.strftime('%A')  # e.g. 'Monday'
        total = Order.objects.filter(tanggal_pesanan__date=day).aggregate(Sum('total_harga'))['total_harga__sum'] or 0

    
    # Hitung total penjualan
    total_penjualan = Order.objects.aggregate(total=Sum('total_harga'))['total'] or 0
    total_gaji_karyawan = Karyawan.objects.aggregate(Sum('total_gaji'))['total_gaji__sum'] or 0
    
        # Cashflow harian
    cashflow_harian = []
    saldo = 0
    for order in Order.objects.filter(tanggal_pesanan__date=today).order_by('tanggal_pesanan'):
        saldo += order.total_harga
        cashflow_harian.append({
            'waktu': order.tanggal_pesanan,
            'keterangan': f"Penjualan {order.kode_bill}",
            'kategori': 'Masuk',
            'jumlah': order.total_harga,
            'saldo': saldo
        })
    return render(request, 'admin/keuanganadm.html', {
        'pendapatan_hari_ini': pendapatan_hari_ini,
        'karyawan_hadir': karyawan_hadir,
        'total_karyawan': total_karyawan,
        'total_penjualan': total_penjualan,
        'total_gaji_karyawan': total_gaji_karyawan,
        'chart_labels': labels,
        'chart_data': data,
        'pendapatan_hari_ini': pendapatan_hari_ini,
        'total_transaksi': total_transaksi,
        'produk_terlaris': produk_terlaris,
        'penjualan_harian': penjualan_harian_qs,
        'cashflow_harian': cashflow_harian
    })


def pos_dashboard(request) :
    today = timezone.localtime().date()

    seven_days_ago = today - timedelta(days=7)  # 7 hari terakhir termasuk hari ini

    # 1. Pendapatan hari ini
    pendapatan_hari_ini = Order.objects.filter(
        tanggal_pesanan__date=today
    ).aggregate(total=Sum('total_harga'))['total'] or 0

    # 2. Total transaksi hari ini
    total_transaksi = Order.objects.filter(
        tanggal_pesanan__date=today
    ).count()

    # 3. Bahan kritis: sisa stok <= batas minimum
    stok_kritis = FoodStock.objects.filter(remaining_stock__lte=10).count()

    # Pendapatan per hari selama 7 hari terakhir
    pendapatan_mingguan_qs = (
        Order.objects
        .filter(tanggal_pesanan__gte=seven_days_ago)
        .annotate(hari=TruncDate('tanggal_pesanan'))
        .values('hari')
        .annotate(total=Sum('total_harga'))
        .order_by('hari')
    )

    # Produk terlaris selama 7 hari terakhir
    produk_terlaris = (
        OrderItem.objects
        .filter(order__tanggal_pesanan__gte=seven_days_ago)
        .values('nama_menu')
        .annotate(jumlah_terjual=Sum('jumlah'), total_pendapatan=Sum('harga'))
        .order_by('-jumlah_terjual')[:5]
    )

    # Data penjualan hari ini
    penjualan_harian_qs = (
        OrderItem.objects
        .select_related('order')
        .filter(order__tanggal_pesanan__date=today)
        .order_by('order__tanggal_pesanan')
    )

    # Riwayat transaksi hari ini
    riwayat_transaksi = (
        Order.objects
        .filter(tanggal_pesanan__date=today)
        .order_by('-tanggal_pesanan')
    )

    # Buat list label & data untuk Chart.js
    labels = [item['hari'].strftime("%d %b") for item in pendapatan_mingguan_qs]
    data = [item['total'] for item in pendapatan_mingguan_qs]

    # Cashflow harian
    cashflow_harian = []
    saldo = 0
    for order in Order.objects.filter(tanggal_pesanan__date=today).order_by('tanggal_pesanan'):
        saldo += order.total_harga
        cashflow_harian.append({
            'waktu': order.tanggal_pesanan,
            'keterangan': f"Penjualan {order.kode_bill}",
            'kategori': 'Masuk',
            'jumlah': order.total_harga,
            'saldo': saldo
        })

    # Data bahan baku hari ini
    bahan_baku_hari_ini = (
        FoodStock.objects
        .select_related('menu_item')
        .filter(date=today)
    )

    karyawans = Karyawan.objects.all()
    total_gaji_karyawan = Karyawan.objects.aggregate(Sum('total_gaji'))['total_gaji__sum'] or 0
    absensi = Karyawan.objects.aggregate(
        total_hadir=Sum('total_kehadiran'),
        total_izin=Sum('total_izin'),
        total_alpha=Sum('total_alpha')
    )
    context = {
        'pendapatan_hari_ini': pendapatan_hari_ini,
        'total_transaksi': total_transaksi,
        'stok_kritis': stok_kritis,
        'chart_labels': labels,
        'chart_data': data,
        'produk_terlaris': produk_terlaris,
        'penjualan_harian': penjualan_harian_qs,
        'riwayat_transaksi': riwayat_transaksi,
        'cashflow_harian': cashflow_harian,
        'data_bahan_baku': bahan_baku_hari_ini,
        'total_hadir': absensi.get('total_hadir') or 0,
        'total_izin': absensi.get('total_izin') or 0,
        'total_alpha': absensi.get('total_alpha') or 0,
        'karyawans': karyawans,
    }
    return render(request, 'admin/posadm.html', context)

def crm_dashboard(request) :
    total_pelanggan = UserProfile.objects.filter(role='crm').count()
    total_produk = MenuItem.objects.count()

    # Ambil waktu sekarang berdasarkan timezone Asia/Jakarta
    today = localtime(timezone.now()).date()
    minggu_ini = today - timedelta(days=7)

    # Filter order yang dibuat hari ini
    pendapatan_hari_ini = Order.objects.filter(
        tanggal_pesanan__date=today
    ).aggregate(total=Sum('total_harga'))['total'] or 0

    # Produk Terlaris
    produk_terlaris = OrderItem.objects.values('nama_menu').annotate(
        total_terjual=Sum('jumlah'),
        total_pendapatan=Sum(F('jumlah') * F('harga'))
    ).order_by('-total_terjual')[:5]

    # Ambil nama pemesan unik + tanggal pertama kali pesan
    pelanggan_list = (
    Order.objects
    .values('nama_pemesan')
    .annotate(tanggal_bergabung=Min('tanggal_pesanan'))
    .order_by('nama_pemesan')
)
 # Filter bulan & tahun dari GET
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')

    # Konversi nama bulan ke angka
    bulan_mapping = {
        'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4,
        'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agustus': 8,
        'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12,
    }

    # Ambil data pembelian
    order_items = OrderItem.objects.select_related('order')
    if bulan and tahun:
        bulan_angka = bulan_mapping.get(bulan)
        if bulan_angka:
            order_items = order_items.filter(
                order__tanggal_pesanan__month=bulan_angka,
                order__tanggal_pesanan__year=int(tahun)
            )

    riwayat_pembelian = order_items.order_by('-order__tanggal_pesanan')

    # Total produk & pendapatan
    total_produk = MenuItem.objects.count()
    total_penjualan = Order.objects.aggregate(total=Sum('total_harga'))['total']

    # Rating Makanan
    rating_list = (
    Rating.objects
    .select_related('item', 'item__order')
    .all()
    )

    # Pendapatan harian selama 7 hari terakhir
    pendapatan_harian_qs = (
        Order.objects
        .filter(tanggal_pesanan__date__gte=minggu_ini)
        .annotate(hari=TruncDate('tanggal_pesanan'))
        .values('hari')
        .annotate(total=Sum('total_harga'))
        .order_by('hari')        
    )

    pendapatan_labels = [item['hari'].strftime("%d %b") for item in pendapatan_harian_qs]
    pendapatan_data = [item['total'] for item in pendapatan_harian_qs]

    # Trend penjualan: jumlah item terjual per hari (7 hari terakhir)
    penjualan_harian_qs = (
        OrderItem.objects
        .filter(order__tanggal_pesanan__date__gte=minggu_ini)
        .annotate(hari=TruncDate('order__tanggal_pesanan'))
        .values('hari')
        .annotate(total_item=Sum('jumlah'))
        .order_by('hari')
    )

    trend_labels = [item['hari'].strftime("%d %b") for item in penjualan_harian_qs]
    trend_data = [item['total_item'] for item in penjualan_harian_qs]

    # Analitik penjualan: total jumlah terjual per produk
    produk_terjual_qs = (
    OrderItem.objects
    .values('nama_menu')
    .annotate(total_terjual=Sum('jumlah'))
    .order_by('-total_terjual')[:5]  # ambil 5 produk terlaris
    )  

    penjualan_labels = [item['nama_menu'] for item in produk_terjual_qs]
    penjualan_data = [item['total_terjual'] for item in produk_terjual_qs]

    
    context = {
        'total_pelanggan': total_pelanggan,
        'total_produk': total_produk,
        'riwayat_pembelian': riwayat_pembelian,
        'pendapatan_hari_ini': pendapatan_hari_ini,
        'produk_terlaris': produk_terlaris,
        'pelanggan_list': pelanggan_list,
        'rating_list': rating_list,
        'pendapatan_labels': pendapatan_labels,
        'pendapatan_data': pendapatan_data,
        'trend_labels': trend_labels,
        'trend_data': trend_data,
        'penjualan_labels': penjualan_labels,
        'penjualan_data': penjualan_data,

    }
    return render(request, 'admin/crmadm.html', context)

def hrd_dashboard(request) :
# Menambahkan Karyawan
    # Inisialisasi semua form
    karyawan_form = KaryawanForm()
    absensi_form = AbsensiForm()

    # Menangani Tambah Karyawan
    if 'create_karyawan' in request.POST:
        karyawan_form = KaryawanForm(request.POST)
        if karyawan_form.is_valid():
            karyawan_form.save()
            messages.success(request, "Karyawan berhasil ditambahkan!")
            return redirect('hrd_dashboard')
        else:
            messages.error(request, "Ada kesalahan dalam pengisian form karyawan!")

    # Menangani Tambah Absensi
    if 'create_absensi' in request.POST:
        absensi_form = AbsensiForm(request.POST)
        if absensi_form.is_valid():
            absensi_form.save()
            messages.success(request, "Absensi berhasil ditambahkan!")
            return redirect('hrd_dashboard')
        else:
            messages.error(request, "Ada kesalahan dalam pengisian form absensi!")
    
    
    # # Menangani Tambah Gaji
    # elif 'create_gaji' in request.POST:
    #     slipgaji_form = SlipGajiForm(request.POST)
    #     if slipgaji_form.is_valid():
    #         slipgaji_form.save()
    #         messages.success(request, "Data gaji berhasil ditambahkan!")
    #         return redirect('hrd_dashboard')
    #     else:
    #         messages.error(request, "Ada kesalahan dalam pengisian form gaji!")
    # Ambil data karyawan
    karyawans = Karyawan.objects.all()

    # Hitung dan simpan gaji terbaru
    for k in karyawans:
        k.hitung_tunjangan = get_tunjangan_divisi(k.divisi)
        gaji_perhari = 80_000 if k.masa_kerja_bulan() < 3 else 100_000
        kehadiran_gaji = k.total_kehadiran * gaji_perhari
        izin_gaji = k.total_izin * (gaji_perhari // 2)
        lembur_gaji = k.lembur_jam * 10_000
        gaji_pokok = k.gaji_pokok
        total = kehadiran_gaji + izin_gaji + lembur_gaji + gaji_pokok + k.hitung_tunjangan

        # Hanya update jika memang perlu
        if k.total_gaji != total:
            k.total_gaji = total
            k.save()

    # Rekap total gaji dan absensi
    total_gaji_karyawan = Karyawan.objects.aggregate(Sum('total_gaji'))['total_gaji__sum'] or 0
    absensi = Karyawan.objects.aggregate(
        total_hadir=Sum('total_kehadiran'),
        total_izin=Sum('total_izin'),
        total_alpha=Sum('total_alpha')
    )


    jumlah_per_jabatan = (
        Karyawan.objects
        .values('jabatan')
        .annotate(jumlah=Count('id'))
        .order_by('jabatan')
    )

    jabatan_labels = [item['jabatan'] for item in jumlah_per_jabatan]
    jabatan_values = [item['jumlah'] for item in jumlah_per_jabatan]

    # Ambil total gaji per jabatan
    gaji_per_jabatan = (
        Karyawan.objects
        .values('jabatan')
        .annotate(total_gaji=Sum('total_gaji'))
        .order_by('jabatan')
    )
    # Pisahkan ke dalam list untuk Chart.js
    gaji_labels = [item['jabatan'] for item in gaji_per_jabatan]
    gaji_values = [item['total_gaji'] or 0 for item in gaji_per_jabatan]

    context = {
        'total_hadir': absensi.get('total_hadir') or 0,
        'total_izin': absensi.get('total_izin') or 0,
        'total_alpha': absensi.get('total_alpha') or 0,
            # Jumlah karyawan per jabatan (untuk Chart.js)
        'jabatan_labels': json.dumps(jabatan_labels),
        'jabatan_values': json.dumps(jabatan_values),

        'gaji_labels': json.dumps(gaji_labels),
        'gaji_values': json.dumps(gaji_values),

        'karyawan_form': karyawan_form,
        'karyawans': karyawans,
        'total_gaji_karyawan': total_gaji_karyawan,
        'absensi_form' : absensi_form,
    }

    return render(request, 'admin/hrdadm.html', context)

def get_tunjangan_divisi(divisi):
    tunjangan_dict = {
        'A': 5_000_000,
        'B': 3_500_000,
        'C': 2_000_000,
        'D': 1_000_000,
    }
    return tunjangan_dict.get(divisi, 0)


def generate_slip_gaji(request):
    if request.method == 'POST':
        karyawan_id = request.POST.get('karyawan_id')
        if not karyawan_id:
            return HttpResponse("ID karyawan tidak ditemukan", status=400)

        try:
            karyawan_id = int(karyawan_id)
        except ValueError:
            return HttpResponse("ID karyawan tidak valid", status=400)

        karyawan = get_object_or_404(Karyawan, id=karyawan_id)

        buffer = BytesIO()
        p = canvas.Canvas(buffer)

        p.drawString(100, 800, f"Slip Gaji Karyawan")
        p.drawString(100, 780, f"Nama: {karyawan.nama_karyawan}")
        p.drawString(100, 760, f"Jabatan: {karyawan.jabatan}")
        p.drawString(100, 740, f"Total Kehadiran: {karyawan.total_kehadiran}")
        p.drawString(100, 720, f"Izin: {karyawan.total_izin}")
        p.drawString(100, 700, f"Alpha: {karyawan.total_alpha}")
        p.drawString(100, 680, f"Lembur: {karyawan.lembur_jam} jam")
        p.drawString(100, 660, f"Total Gaji: Rp {karyawan.total_gaji:,.0f}")

        p.showPage()
        p.save()

        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Slip_Gaji_{karyawan.nama_karyawan}.pdf"'
        return response
        return HttpResponse("Method not allowed", status=405)

def update_karyawan(request):
    if request.method == 'POST':
        id = request.POST.get('karyawan_id')
        karyawan = get_object_or_404(Karyawan, id=id)
        karyawan.nama_karyawan = request.POST.get('nama_karyawan')
        karyawan.jabatan = request.POST.get('jabatan')
        karyawan.gaji_pokok = request.POST.get('gaji_pokok')
        karyawan.save()
        messages.success(request, "Karyawan berhasil diperbarui.")
    return redirect('hrd_dashboard')

def hapus_karyawan(request, id):
    karyawan = get_object_or_404(Karyawan, id=id)
    if request.method == 'POST':
        karyawan.delete()
        messages.success(request, "Karyawan berhasil dihapus.")
    return redirect('hrd_dashboard')

def update_absensi(request):
    if request.method == 'POST':
        id = request.POST.get('karyawan_id')
        karyawan = get_object_or_404(Karyawan, id=id)
        karyawan.nama_karyawan = request.POST.get('nama_karyawan')
        karyawan.total_kehadiran = request.POST.get('total_kehadiran')
        karyawan.total_izin = request.POST.get('total_izin')
        karyawan.total_alpha = request.POST.get('total_alpha')
        karyawan.save()
        messages.success(request, "Absensi berhasil diperbarui.")
    return redirect('hrd_dashboard')
    
