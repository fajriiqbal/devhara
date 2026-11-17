from datetime import date

from django.test import TestCase
from django.urls import reverse

from bendahara.models import (
    JenisPembayaran,
    KasKeluar,
    KasKeluarAlokasi,
    Pembayaran,
    PemasukanNonSiswa,
    Semester,
    Siswa,
    Tagihan,
)


class MonitoringBendaharaTests(TestCase):
    def test_monitoring_includes_non_student_income_and_category_allocations(self):
        semester = Semester.objects.create(
            nama='Ganjil 2026/2027',
            tahun_ajaran='2026/2027',
            semester='Ganjil',
            tanggal_mulai=date(2026, 7, 1),
            tanggal_selesai=date(2026, 12, 31),
            aktif=True,
        )
        siswa = Siswa.objects.create(nis='MON-001', nama='Siswa Monitoring', kelas='7A')
        jenis = JenisPembayaran.objects.create(nama='SPP Monitoring', nominal_default=1000)
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
        kas_keluar = KasKeluar.objects.create(
            judul='Konsumsi kegiatan',
            kategori='Konsumsi',
            jumlah=100,
            semester=semester,
        )
        KasKeluarAlokasi.objects.create(
            kas_keluar=kas_keluar,
            kategori_pemasukan_non_siswa='Donasi',
            nominal=100,
        )

        response = self.client.get(reverse('monitoring_bendahara'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_target_masuk'], 1000)
        self.assertEqual(response.context['total_pembayaran_siswa'], 200)
        self.assertEqual(response.context['total_pemasukan_non_siswa'], 500)
        self.assertEqual(response.context['total_kas_masuk'], 700)
        self.assertEqual(response.context['total_sisa'], 800)
        self.assertEqual(response.context['total_pengeluaran'], 100)
        self.assertEqual(response.context['saldo_aktual'], 600)

        category_row = response.context['non_student_category_summary_rows'][0]
        self.assertEqual(category_row['kategori'], 'Donasi')
        self.assertEqual(category_row['masuk'], 500)
        self.assertEqual(category_row['keluar'], 100)
        self.assertEqual(category_row['saldo'], 400)
        self.assertContains(response, 'Pemasukan Non-Siswa - Donasi')
