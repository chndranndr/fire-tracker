# ADR 002 — Framing kampanye / lensa politik

## Status

Accepted

## Konteks

Brief meminta investigasi politik: jaringan konsesi–modal–parpol ditonjolkan. Risiko: UI terbaca sebagai vonis pidana atau “parpol membakar hutan”.

## Keputusan

- **IkatanPolitik adalah lensa utama UI** (panel Temuan, filter partai, hub graf Party), bukan bukti pembakaran.
- Panel Temuan menonjolkan statistik WALHI (74% di konsesi), ranking 12 konsesi, dan tautan yang bisa dikutip (mis. Golkar–Bakrie–KPC; Gerindra–Kiani) **dengan caveat**.
- Warna partai hanya sebagai tag inspector, bukan efek visual yang menyiratkan culpability.
- Copy menghindari vonis pidana; tidak mengisi UBO/parpol tanpa sumber → `UNKNOWN` / `TIDAK TERPETAKAN`.
- Kiani Lestari selalu menampilkan caveat operasional Gecko Project.

## Konsekuensi

- Filter dan graf memusatkan Party sebagai hub navigasi.
- Klaim politik tanpa NamedSource dilarang di data dossier.
- Framing “temuan” = jaringan yang dapat dilacak dari sumber terbuka, bukan atribusi api.
