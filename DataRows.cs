namespace V3.Api.Models;

/// <summary>inflation_series.csv satiri: country_code,month,inflation_yoy</summary>
public sealed class InflationPoint
{
    public string CountryCode { get; set; } = "";
    public string Month { get; set; } = "";      // "2024-07"
    public double InflationYoy { get; set; }

    public static List<InflationPoint> Load(string path) =>
        File.Exists(path)
            ? File.ReadLines(path).Skip(1)
                .Select(l => l.Split(','))
                .Where(p => p.Length >= 3 && double.TryParse(p[2], out _))
                .Select(p => new InflationPoint
                {
                    CountryCode = p[0].Trim(),
                    Month = p[1].Trim(),
                    InflationYoy = double.Parse(p[2]),
                }).ToList()
            : new();
}

/// <summary>panel_dataset.csv satiri (secim bazli).</summary>
public sealed class PanelRow
{
    public string CountryCode { get; set; } = "";
    public DateTime ElectionDate { get; set; }
    public Dictionary<string, double> Features { get; } = new();

    public static List<PanelRow> Load(string path)
    {
        if (!File.Exists(path)) return new();
        var rows = new List<PanelRow>();
        var lines = File.ReadLines(path).ToList();
        var header = lines[0].Split(',');
        int ixCode = Array.IndexOf(header, "country_code");
        int ixDate = Array.IndexOf(header, "election_date");

        foreach (var line in lines.Skip(1))
        {
            var p = line.Split(',');
            if (p.Length < header.Length) continue;
            var row = new PanelRow
            {
                CountryCode = p[ixCode].Trim(),
                ElectionDate = DateTime.TryParse(p[ixDate], out var d) ? d : default,
            };
            for (int i = 0; i < header.Length; i++)
            {
                var h = header[i].Trim();
                if (h is "country_code" or "election_date" or "is_eu_member"
                    or "govt_change") continue;
                if (double.TryParse(p[i], out var v))
                    row.Features[h] = v;
            }
            rows.Add(row);
        }
        return rows;
    }
}
