namespace SensorPublisher.Core;

/// <summary>
/// Minimal catalog for MVP.
/// Replace/extend this with the real sensor_dict mapping from your Python code when ready.
/// </summary>
public static class SensorCatalog
{
    public static IReadOnlyList<int> Floors { get; } = Enumerable.Range(1, 10).ToList();
    public static IReadOnlyList<string> Sections { get; } = new[] { "A", "B" };

    // Example energy IDs. Replace with your actual IDs.
    public static IReadOnlyList<string> EnergyIds { get; } = new[]
    {
        "1209","1221","1225","1227","1231","1233","1237","1243","1245","1247"
    };

    public static IEnumerable<PowerKey> AllPowerKeys()
        => from f in Floors
           from s in Sections
           select new PowerKey(f, s);

    public static IEnumerable<WaterKey> AllWaterKeys()
        => from f in Floors
           select new WaterKey(f);

    public static IEnumerable<EnergyKey> AllEnergyKeys()
        => from f in Floors
           from id in EnergyIds
           select new EnergyKey(f, id);
}
