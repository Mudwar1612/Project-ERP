from django import forms
from .models import Karyawan

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class KaryawanForm(forms.ModelForm):
    JENIS_KELAMIN_CHOICES = [
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    ]
    j_kelamin = forms.ChoiceField(choices=JENIS_KELAMIN_CHOICES)
    class Meta:
        model = Karyawan
        fields = ['nama_karyawan','jabatan','j_kelamin','alamat', 'kontak', 'no_rekening','divisi','gaji_pokok', 'tanggal_masuk', 'total_kehadiran', 'total_izin', 'total_alpha','lembur_jam']

        widgets = {
            'tanggal_masuk': forms.DateInput(attrs={'type': 'date'}),
        }
        
class AbsensiForm(forms.ModelForm):
    class Meta:
        model = Karyawan
        fields = ['nama_karyawan','jabatan','total_kehadiran', 'total_izin', 'total_alpha', 'total_izin', 'total_alpha']