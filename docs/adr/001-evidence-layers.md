# ADR 001 — Empat lapisan bukti terpisah

## Status

Accepted

## Konteks

Dashboard MERATUS menggabungkan deteksi satelit, klaim overlay konsesi WALHI, kepemilikan korporasi, dan ikatan politik. Pengguna mudah membaca keempatnya sebagai satu fakta (“perusahaan X milik partai Y membakar hutan”).

## Keputusan

Empat lapisan **tidak boleh dilipat** menjadi satu klaim di UI atau data:

1. **Detection** — titik/cluster FIRMS (termal satelit).
2. **ConcessionClaim** — overlay WALHI (hotspot agregat di dalam konsesi, periode Jan–Jul 2026).
3. **Control** — Company → Group → Person / UBO dari sumber publik bernama.
4. **PoliticalTie** — jabatan partai, peran kampanye, kekerabatan, kabinet — dengan NamedSource.

Tepi graf berlabel eksplisit (`KLAIM_OVERLAY`, `KONTROL`, `IKATAN`). Tooltip FIRMS hanya menampilkan deteksi; overlay perusahaan menjelaskan klaim WALHI + lokasi operasi, bukan join GIS live.

## Konsekuensi

- Tidak ada join FIRMS 7 hari × poligon HGU/IUP di produk ini.
- Copy UI wajib membedakan deteksi vs klaim konsesi vs kontrol vs politik.
- Invariant: Detection ≠ kebakaran terverifikasi; hotspot di konsesi ≠ pelaku pembakaran.
