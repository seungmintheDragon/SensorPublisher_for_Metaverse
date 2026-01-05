using System.Collections.Immutable;

namespace SensorPublisher.Core;

/// <summary>
/// Default selection: if empty for a type, it means "allow all".
/// Manual overrides: keys in Override are excluded from default publishing.
/// </summary>
public sealed class SelectionState
{
    private readonly object _lock = new();

    private ImmutableHashSet<PowerKey> _power = ImmutableHashSet<PowerKey>.Empty;
    private ImmutableHashSet<WaterKey> _water = ImmutableHashSet<WaterKey>.Empty;
    private ImmutableHashSet<EnergyKey> _energy = ImmutableHashSet<EnergyKey>.Empty;

    private ImmutableHashSet<PowerKey> _overridePower = ImmutableHashSet<PowerKey>.Empty;
    private ImmutableHashSet<WaterKey> _overrideWater = ImmutableHashSet<WaterKey>.Empty;
    private ImmutableHashSet<EnergyKey> _overrideEnergy = ImmutableHashSet<EnergyKey>.Empty;

    public (ImmutableHashSet<PowerKey> selected, ImmutableHashSet<PowerKey> overridden) SnapshotPower()
    {
        lock (_lock) return (_power, _overridePower);
    }

    public (ImmutableHashSet<WaterKey> selected, ImmutableHashSet<WaterKey> overridden) SnapshotWater()
    {
        lock (_lock) return (_water, _overrideWater);
    }

    public (ImmutableHashSet<EnergyKey> selected, ImmutableHashSet<EnergyKey> overridden) SnapshotEnergy()
    {
        lock (_lock) return (_energy, _overrideEnergy);
    }

    public void SetDefaultPower(IEnumerable<PowerKey> keys)
    {
        lock (_lock) _power = keys.ToImmutableHashSet();
    }

    public void SetDefaultWater(IEnumerable<WaterKey> keys)
    {
        lock (_lock) _water = keys.ToImmutableHashSet();
    }

    public void SetDefaultEnergy(IEnumerable<EnergyKey> keys)
    {
        lock (_lock) _energy = keys.ToImmutableHashSet();
    }

    public void AddOverridePower(IEnumerable<PowerKey> keys)
    {
        lock (_lock) _overridePower = _overridePower.Union(keys);
    }

    public void RemoveOverridePower(IEnumerable<PowerKey> keys)
    {
        lock (_lock) _overridePower = _overridePower.Except(keys);
    }

    public void AddOverrideWater(IEnumerable<WaterKey> keys)
    {
        lock (_lock) _overrideWater = _overrideWater.Union(keys);
    }

    public void RemoveOverrideWater(IEnumerable<WaterKey> keys)
    {
        lock (_lock) _overrideWater = _overrideWater.Except(keys);
    }

    public void AddOverrideEnergy(IEnumerable<EnergyKey> keys)
    {
        lock (_lock) _overrideEnergy = _overrideEnergy.Union(keys);
    }

    public void RemoveOverrideEnergy(IEnumerable<EnergyKey> keys)
    {
        lock (_lock) _overrideEnergy = _overrideEnergy.Except(keys);
    }
}
