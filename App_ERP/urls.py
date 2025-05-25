from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import simpan_pesanan, sukses

urlpatterns = [
    path('', views.start, name='start'),
    path('menu', views.menu, name='menu'),
    path('payment', views.payment, name='payment'),
    path("simpan_pesanan/", simpan_pesanan, name="simpan_pesanan"),
    path('sukses/', sukses, name='sukses'),
    path('ratting/<str:kode_bill>/', views.ratting, name='ratting'),
    path('loginadm/', views.login_view, name='login_view'),
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('inventori/', views.inventori_dashboard, name='inventori_dashboard'),
    path('produksi/', views.produksi_dashboard, name='produksi_dashboard'),
    path('pos/', views.pos_dashboard, name='pos_dashboard'),
    path('keuangan/', views.keuangan_dashboard, name='keuangan_dashboard'),
    path('crm/', views.crm_dashboard, name='crm_dashboard'),
    path('hrd/', views.hrd_dashboard, name='hrd_dashboard'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('generate_slip_gaji/', views.generate_slip_gaji, name='generate_slip_gaji'),
    #path('profile-missing/', views, name='profile_missing'),
    #path('unknown-role/', views, name='unknown_role'),
    path('karyawan/update/', views.update_karyawan, name='update_karyawan'),
    path('karyawan/hapus/<int:id>/', views.hapus_karyawan, name='hapus_karyawan'),
    path('karyawan/update/absensi/', views.update_absensi, name='update_absensi'),
    
]