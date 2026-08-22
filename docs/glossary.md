# Glossary — MERATUS

Istilah domain untuk dashboard intel karhutla Kalimantan. Digunakan konsisten di UI, dossier, dan ADR.

## Hotspot

Deteksi termal satelit (biasanya VIIRS/MODIS via NASA FIRMS) yang menandai suhu permukaan anomali. **Bukan** verifikasi lapangan bahwa terjadi kebakaran aktif atau bahwa suatu pihak menyulut api.

## HighConfidence / Keyakinan deteksi

Tingkat keyakinan algoritma FIRMS terhadap deteksi termal (`low` / `nominal` / `high`, atau nilai numerik tergantung produk). Keyakinan deteksi ≠ keyakinan atribusi ke perusahaan atau aktor politik.

## Konsesi

Area izin pemanfaatan lahan (HGU, IUP tambang, PBPH/HTI, dll.). Di MERATUS, klaim "hotspot di dalam konsesi" berasal dari overlay WALHI (Jan–Jul 2026), **bukan** join GIS live FIRMS × poligon resmi di repo ini.

## HGU

Hak Guna Usaha — izin konsesi pertanian/perkebunan (sering sawit). Di data WALHI: subset hotspot di dalam HGU sawit.

## PBPH

Persetujuan Berusaha Pemanfaatan Hutan (dahulu sering disebut HTI/izin hutan tanaman). Di dossier MERATUS: sektor PBPH untuk konsesi seperti Dwima Intiga dan Kiani Lestari.

## UBO

*Ultimate Beneficial Owner* — pemilik manfaat / pengendali akhir yang dapat dikutip dari sumber publik bernama. Jika tidak terkunci: status `UNKNOWN` / `UBO UNKNOWN`, tanpa spekulasi grup.

## IkatanPolitik

Hubungan yang dapat dikutip antara orang/grup dan partai, kampanye, jabatan partai, kekerabatan elite, atau peran kabinet/koalisi. **Bukan** bukti bahwa partai atau pejabat membakar hutan. Jika tidak ada sumber: `TIDAK TERPETAKAN`.

## Sumber / NamedSource

Rujukan publik bernama (URL, lembaga, tanggal) yang menopang klaim di dossier. Setiap klaim UBO, kontrol saham, atau ikatan politik harus punya sumber yang bisa diklik di inspector.

## Keyakinan (sumber)

Tingkat kekuatan bukti untuk klaim dossier (bukan FIRMS): misalnya `tinggi` (dokumen/pernyataan resmi berulang), `sedang` (pemberitaan investigatif), `rendah` / caveat (klaim historis, operasional diragukan). Ditampilkan eksplisit di UI.

## Detection / FireCluster

Lapisan deteksi FIRMS (titik atau cluster spasial-temporal). Terpisah dari klaim konsesi WALHI.

## ConcessionClaim

Klaim overlay WALHI bahwa hotspot periode tertentu jatuh di dalam konsesi bernama, dengan angka hotspot agregat — bukan atribusi penyebab api.

## Company / CorporateGroup / Person / Party

Entitas graf objek: perusahaan konsesi → grup kontrol → orang → partai/ikatan. Tepi berlabel (`KLAIM_OVERLAY`, `KONTROL`, `IKATAN`) agar relasi tidak dibaca sebagai satu fakta tunggal.
