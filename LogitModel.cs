namespace V3.Api.Models;

/// <summary>
/// Python (statsmodels) tarafindan uretilen lojistik regresyon katsayilari.
/// Semaya birebir uyum icin data_prep_v2.py icindeki export_models_json ile
/// ayni alan adlari kullanilir: name, intercept, coefficients, aic.
/// </summary>
public sealed class LogitModel
{
    public string Name { get; set; } = "";
    public double Intercept { get; set; }
    public Dictionary<string, double> Coefficients { get; set; } = new();
    public double Aic { get; set; }

    public double PredictProbability(IReadOnlyDictionary<string, double> features)
    {
        var z = Intercept;
        foreach (var (key, beta) in Coefficients)
            if (features.TryGetValue(key, out var x))
                z += beta * x;
        return 1.0 / (1.0 + Math.Exp(-z)); // sigmoid
    }
}
