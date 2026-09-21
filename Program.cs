using System.Text.Json;
using V3.Api.Models;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(options =>
    options.AddDefaultPolicy(p =>
        p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));

var app = builder.Build();

app.UseDefaultFiles();
app.UseStaticFiles();
app.UseCors();

var dataDir = Path.Combine(AppContext.BaseDirectory, "Data");
if (!Directory.Exists(dataDir))
    dataDir = AppContext.BaseDirectory;

var models = JsonSerializer.Deserialize<List<LogitModel>>(
    File.ReadAllText(Path.Combine(dataDir, "models.json")),
    new JsonSerializerOptions { PropertyNameCaseInsensitive = true }) ?? new();

var panel = PanelRow.Load(Path.Combine(dataDir, "panel_dataset.csv"));
var inflation = InflationPoint.Load(Path.Combine(dataDir, "inflation_series.csv"));

app.MapGet("/api/health", () => Results.Ok(new
{
    status = "ok",
    models = models.Count,
    elections = panel.Count,
    inflationPoints = inflation.Count,
    placeholderWarning = models.Any(m => m.Intercept == 0.0 && m.Coefficients.Values.All(v => v == 0.0)),
}));

app.MapGet("/api/countries", () =>
{
    var countries = panel
        .Select(r => r.CountryCode.ToUpperInvariant())
        .Distinct()
        .OrderBy(code => code)
        .Select(code => new { code, name = code })
        .ToList();

    return Results.Ok(countries);
});

app.MapGet("/api/models", () => Results.Ok(models));

app.MapGet("/api/inflation/{countryCode}", (string countryCode) =>
{
    var series = inflation
        .Where(p => p.CountryCode.Equals(countryCode, StringComparison.OrdinalIgnoreCase))
        .OrderBy(p => p.Month)
        .ToList();

    return series.Count == 0 ? Results.NotFound() : Results.Ok(series);
});

app.MapGet("/api/risk/{countryCode}", (string countryCode) =>
{
    var row = panel
        .Where(r => r.CountryCode.Equals(countryCode, StringComparison.OrdinalIgnoreCase))
        .OrderByDescending(r => r.ElectionDate)
        .FirstOrDefault();

    if (row is null)
        return Results.NotFound(new { error = "country not in panel" });

    var probs = models.Select(m => new
    {
        model = m.Name,
        probability = Math.Round(m.PredictProbability(row.Features), 4),
    }).ToList();

    return Results.Ok(new
    {
        country = countryCode.ToUpperInvariant(),
        election = row.ElectionDate.ToString("yyyy-MM-dd"),
        estimatedProbabilities = probs,
        features = row.Features,
    });
});

app.MapFallbackToFile("index.html");

app.Run();
