from django.shortcuts import render
from django.db.models import Prefetch, Sum
from django.db.models.functions import Coalesce
from django.utils.timezone import localdate

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

def home(request):
    semester_aktif = Semester.objects.filter(aktif=True).first()
    return render(request, 'core/home.html', {
        'semester_aktif': semester_aktif,
    })


def monitoring_bendahara(request):
    today = localdate()
    semester_aktif = Semester.objects.filter(aktif=True).first()

    if semester_aktif:
        tagihan_queryset = (
            Tagihan.objects.filter(semester=semester_aktif)
            .select_related('siswa', 'jenis', 'semester')
            .prefetch_related('pembayaran_set')
        )
        pembayaran_queryset = (
            Pembayaran.objects.select_related(
                'transaksi',
                'tagihan__siswa',
                'tagihan__jenis',
                'tagihan__semester',
            )
            .filter(tagihan__semester=semester_aktif)
            .order_by('-tanggal_bayar')
        )
        kas_keluar_queryset = (
            KasKeluar.objects.filter(semester=semester_aktif)
            .select_related('jenis_pembayaran')
            .prefetch_related('alokasi_set__jenis_pembayaran')
            .order_by('-tanggal_pengeluaran', '-id')
        )
        pemasukan_non_siswa_queryset = (
            PemasukanNonSiswa.objects.filter(semester=semester_aktif)
            .order_by('-tanggal_pemasukan', '-id')
        )
    else:
        tagihan_queryset = Tagihan.objects.none()
        pembayaran_queryset = Pembayaran.objects.none()
        kas_keluar_queryset = KasKeluar.objects.none()
        pemasukan_non_siswa_queryset = PemasukanNonSiswa.objects.none()

    tagihan_items = list(tagihan_queryset)
    pembayaran_items = list(pembayaran_queryset[:8])
    kas_keluar_items = list(kas_keluar_queryset[:6])
    pemasukan_non_siswa_items = list(pemasukan_non_siswa_queryset[:6])

    total_siswa_aktif = Siswa.objects.filter(aktif=True).count()
    total_jenis_pembayaran_aktif = JenisPembayaran.objects.filter(aktif=True).count()
    total_tagihan = len(tagihan_items)
    total_target_masuk = sum(tagihan.nominal for tagihan in tagihan_items)
    total_pembayaran_siswa = sum(tagihan.total_terbayar for tagihan in tagihan_items)
    total_pemasukan_non_siswa = pemasukan_non_siswa_queryset.aggregate(
        total=Coalesce(Sum('jumlah'), 0)
    )['total']
    total_kas_masuk = total_pembayaran_siswa + total_pemasukan_non_siswa
    total_sisa = max(total_target_masuk - total_pembayaran_siswa, 0)
    total_pengeluaran = sum(item.jumlah for item in kas_keluar_queryset)
    saldo_aktual = total_kas_masuk - total_pengeluaran

    non_student_category_income_rows = (
        pemasukan_non_siswa_queryset.exclude(kategori='')
        .values('kategori')
        .annotate(total=Coalesce(Sum('jumlah'), 0))
    )
    non_student_category_summary = {
        row['kategori']: {
            'kategori': row['kategori'],
            'masuk': row['total'],
            'keluar': 0,
        }
        for row in non_student_category_income_rows
    }
    non_student_allocations = []
    if semester_aktif:
        non_student_allocations = (
            KasKeluarAlokasi.objects.filter(
                kas_keluar__semester=semester_aktif,
                kategori_pemasukan_non_siswa__isnull=False,
            )
            .values('kategori_pemasukan_non_siswa')
            .annotate(total=Coalesce(Sum('nominal'), 0))
        )
    for row in non_student_allocations:
        category = row['kategori_pemasukan_non_siswa']
        category_summary = non_student_category_summary.setdefault(category, {
            'kategori': category,
            'masuk': 0,
            'keluar': 0,
        })
        category_summary['keluar'] = row['total']
    non_student_category_summary_rows = list(non_student_category_summary.values())
    for row in non_student_category_summary_rows:
        row['saldo'] = row['masuk'] - row['keluar']
    non_student_category_summary_rows.sort(
        key=lambda row: (row['masuk'], row['kategori'].casefold()),
        reverse=True,
    )

    for kas_keluar in kas_keluar_items:
        allocations = list(kas_keluar.alokasi_set.all())
        if allocations:
            kas_keluar.monitoring_allocation_rows = [
                {
                    'label': (
                        f'Jenis Pembayaran - {allocation.jenis_pembayaran.nama}'
                        if allocation.jenis_pembayaran_id
                        else f'Pemasukan Non-Siswa - {allocation.kategori_pemasukan_non_siswa}'
                    ),
                    'nominal': allocation.nominal,
                }
                for allocation in allocations
            ]
        elif kas_keluar.jenis_pembayaran_id:
            kas_keluar.monitoring_allocation_rows = [{
                'label': f'Jenis Pembayaran - {kas_keluar.jenis_pembayaran.nama}',
                'nominal': kas_keluar.jumlah,
            }]
        else:
            kas_keluar.monitoring_allocation_rows = []

    siswa_objects = (
        Siswa.objects.filter(aktif=True)
        .prefetch_related(
            Prefetch(
                'tagihan_set',
                queryset=tagihan_queryset,
            )
        )
        .order_by('nama')
    )

    siswa_tunggakan = []
    pondok_summary_map = {}
    for siswa in siswa_objects:
        siswa_tagihan = list(siswa.tagihan_set.all())
        if not siswa_tagihan:
            continue

        siswa_total_sisa = sum(tagihan.sisa_tagihan for tagihan in siswa_tagihan)
        if siswa_total_sisa > 0:
            siswa_tunggakan.append({
                'siswa': siswa,
                'total_sisa': siswa_total_sisa,
                'jumlah_item': sum(1 for tagihan in siswa_tagihan if tagihan.sisa_tagihan > 0),
            })

            pondok_key = siswa.pondok or 'Belum Diisi'
            if pondok_key not in pondok_summary_map:
                pondok_summary_map[pondok_key] = {
                    'pondok': pondok_key,
                    'jumlah_siswa': 0,
                    'total_sisa': 0,
                }
            pondok_summary_map[pondok_key]['jumlah_siswa'] += 1
            pondok_summary_map[pondok_key]['total_sisa'] += siswa_total_sisa

    siswa_tunggakan.sort(key=lambda item: item['total_sisa'], reverse=True)
    pondok_summary_rows = sorted(
        pondok_summary_map.values(),
        key=lambda item: item['total_sisa'],
        reverse=True,
    )

    jenis_summary_map = {}
    for tagihan in tagihan_items:
        jenis_summary_map.setdefault(tagihan.jenis_id, {
            'jenis': tagihan.jenis,
            'target': 0,
            'masuk': 0,
            'sisa': 0,
        })
        jenis_summary_map[tagihan.jenis_id]['target'] += tagihan.nominal
        jenis_summary_map[tagihan.jenis_id]['masuk'] += tagihan.total_terbayar
        jenis_summary_map[tagihan.jenis_id]['sisa'] += tagihan.sisa_tagihan
    jenis_summary_rows = sorted(jenis_summary_map.values(), key=lambda item: item['target'], reverse=True)

    context = {
        'today': today,
        'semester_aktif': semester_aktif,
        'total_siswa_aktif': total_siswa_aktif,
        'total_jenis_pembayaran_aktif': total_jenis_pembayaran_aktif,
        'total_tagihan': total_tagihan,
        'total_target_masuk': total_target_masuk,
        'total_pembayaran_siswa': total_pembayaran_siswa,
        'total_pemasukan_non_siswa': total_pemasukan_non_siswa,
        'total_kas_masuk': total_kas_masuk,
        'total_sisa': total_sisa,
        'total_pengeluaran': total_pengeluaran,
        'saldo_aktual': saldo_aktual,
        'pembayaran_items': pembayaran_items,
        'pemasukan_non_siswa_items': pemasukan_non_siswa_items,
        'non_student_category_summary_rows': non_student_category_summary_rows,
        'kas_keluar_items': kas_keluar_items,
        'siswa_tunggakan': siswa_tunggakan[:8],
        'pondok_summary_rows': pondok_summary_rows[:8],
        'jenis_summary_rows': jenis_summary_rows[:8],
    }
    return render(request, 'core/monitoring_bendahara.html', context)
