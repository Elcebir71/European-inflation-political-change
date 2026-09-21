# =============================================================================
# V3.Api — Multi-stage Dockerfile (.NET 8)
# Veri akisi: data_prep_v2.py -> Data/ (models.json, panel_dataset.csv,
#             inflation_series.csv) -> API
# Not: models.json placeholder'dir; gercek katsayilar Python koşusu sonrasi
# volume ile inject edilir (bkz. docker-compose.yml).
# =============================================================================

# ---------- 1. Build stage ----------
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# csproj'i once kopyala -> restore katmani cache'lenir, kod degisince
# NuGet restore tekrar calismaz (Docker layer cache optimizasyonu)
COPY V3.Api.csproj .
RUN dotnet restore

# Geri kalan her sey -> yayinla
COPY . .
RUN dotnet publish -c Release -o /app/publish --no-restore


# ---------- 2. Runtime stage ----------
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime

# Kuresel kultur + non-root kullanici (container guvenligi)
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false     ASPNETCORE_URLS=http://+:8080

WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

COPY --from=build /app/publish .

# Data/ csproj uzerinden publish ciktisina kopyalanir (PreserveNewest);
# gercek model artefactlari docker-compose volume'i ile uzerine binilir.
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3   CMD wget -qO- http://localhost:8080/api/health || exit 1

ENTRYPOINT ["dotnet", "V3.Api.dll"]
