from datetime import date

from django.test import TestCase
from django.urls import reverse

from .forms import PemasukanNonSiswaForm
from .models import (
    KasKeluar,
    JenisPembayaran,
    Pembayaran,
    PemasukanNonSiswa,
    Semester,
    Siswa,
    Tagihan,
)
from .views import get_cash_position_summary, get_kas_summary


class PemasukanNonSiswaTests(TestCase):
    def test_page_creates_and_updates_non_student_income(self):
        semester = Semester.objects.create(
            nama='Ganjil 2026/2027',
            tahun_ajaran='2026/2027',
            semester='Ganjil',
            tanggal_mulai=date(2026, 7, 1),
            tanggal_selesai=date(2026, 12, 31),
            aktif=True,
        )
        page_url = reverse('bendahara:pemasukan_non_siswa')

        self.assertEqual(self.client.get(page_url).status_code, 200)
        response = self.client.post(page_url, {
            'judul': 'Donasi kegiatan',
            'kategori': 'Donasi',
            'jumlah': '7500',
            'tanggal_pemasukan': '2026-11-17',
            'semester': str(semester.pk),
            'keterangan': 'Sumbangan kegiatan sekolah',
        })

        self.assertEqual(response.status_code, 302)
        pemasukan = PemasukanNonSiswa.objects.get(judul='Donasi kegiatan')
        self.assertEqual(pemasukan.semester, semester)
        self.assertEqual(pemasukan.kode_pemasukan, f'PN-20261117-{pemasukan.pk:04d}')

        update_response = self.client.post(
            reverse('bendahara:pemasukan_non_siswa_update', args=[pemasukan.pk]),
            {
                'judul': 'Donasi kegiatan diperbarui',
                'kategori': 'Donasi',
                'jumlah': '9000',
                'tanggal_pemasukan': '2026-11-17',
                'semester': str(semester.pk),
                'keterangan': 'Nominal dikoreksi',
            },
        )

        self.assertEqual(update_response.status_code, 302)
        pemasukan.refresh_from_db()
        self.assertEqual(pemasukan.judul, 'Donasi kegiatan diperbarui')
        self.assertEqual(pemasukan.jumlah, 9000)

    def test_form_rejects_non_positive_amount(self):
        form = PemasukanNonSiswaForm(data={
            'judul': 'Donasi kegiatan',
            'kategori': 'Donasi',
            'jumlah': '0',
            'tanggal_pemasukan': '2026-11-17',
            'semester': '',
            'keterangan': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('jumlah', form.errors)

    def test_cash_summaries_include_non_student_income_without_reducing_student_arrears(self):
        semester = Semester.objects.create(
            nama='Ganjil 2026/2027',
            tahun_ajaran='2026/2027',
            semester='Ganjil',
            tanggal_mulai=date(2026, 7, 1),
            tanggal_selesai=date(2026, 12, 31),
            aktif=True,
        )
        siswa = Siswa.objects.create(nis='TEST-001', nama='Siswa Uji', kelas='7A')
        jenis = JenisPembayaran.objects.create(
            nama='SPP Uji',
            nominal_default=1000,
        )
        tagihan = Tagihan.objects.create(
            siswa=siswa,
            jenis=jenis,
            semester=semester,
            nominal=1000,
        )
        Pembayaran.objects.create(tagihan=tagihan, jumlah_bayar=200)
        PemasukanNonSiswa.objects.create(
            judul='Donasi kegiatan',
            kategori='Donasi',
            jumlah=500,
            semester=semester,
        )
        KasKeluar.objects.create(
            judul='Belanja kegiatan',
            kategori='Operasional',
            jumlah=100,
            semester=semester,
        )

        cash_position = get_cash_position_summary(semester)
        kas_summary = get_kas_summary(semester)

        self.assertEqual(cash_position['total_realisasi_masuk'], 700)
        self.assertEqual(cash_position['total_pemasukan_non_siswa'], 500)
        self.assertEqual(cash_position['saldo_aktual'], 600)
        self.assertEqual(cash_position['sisa_target_belum_masuk'], 800)
        self.assertEqual(kas_summary['total_kas_masuk'], 700)
        self.assertEqual(kas_summary['saldo_kas'], 600)
