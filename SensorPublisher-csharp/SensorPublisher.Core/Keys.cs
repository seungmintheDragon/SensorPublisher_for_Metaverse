namespace SensorPublisher.Core;

public enum DataType
{
    Power,
    Water,
    Energy
}

public readonly record struct PowerKey(int Floor, string Section);
public readonly record struct WaterKey(int Floor);
public readonly record struct EnergyKey(int Floor, string EnergyId);
