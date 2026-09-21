# V3.Api (.NET 8 Minimal API)

## Veri akisi
1. `python data_prep_v2.py` -> uretir:
   - `panel_dataset.csv`   (secim bazli panel)
   - `inflation_series.csv` (aylik enflasyon serisi)
   - `models.json`          (V1/V2/V3 lojistik katsayilari + AIC)
2. Uc dosyayi `Data/` klasorune kopyala.
3. `dotnet run` -> http://localhost:5000

## Endpoint'ler
- GET /api/health
- GET /api/models
- GET /api/inflation/{countryCode}   ornek: /api/inflation/DE
- GET /api/risk/{countryCode}        ornek: /api/risk/GB

## Notlar
- Ulke kodlari ISO 3166-1 alpha-2: Birlesik Krallik = GB, Ukrayna = UA.
- /api/risk olasilik URETIR; bu bir istatistiksel iliskidir, kehanet degil.
  Uygulama icerisinde "risk skoru" olarak sunulmali.
- models.json ici placeholder'dir; Python scripti calisinca gercek katsayilarla
  otomatik guncellenir (sema ayni kalir).
