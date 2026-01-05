using System.Collections.Immutable;

namespace SensorPublisher.Core;

/// <summary>
/// Default publisher that emits Power/Water/Energy periodically based on:
/// - Default selection (empty selection => allow all)
/// - Override set (excluded from default while manual session is running)
///
/// For MVP: payloads are random; integrate CSV scenario later.
/// </summary>
public sealed class DefaultDataWorker
{
    private readonly IMqttPublisher _mqtt;
    private readonly MqttSettings _settings;
    private readonly IAppLogger _log;
    private readonly SelectionState _state;

    private CancellationTokenSource? _cts;
    private Task? _loop;

    public bool IsRunning => _cts is not null && !_cts.IsCancellationRequested;

    public DefaultDataWorker(IMqttPublisher mqtt, MqttSettings settings, SelectionState state, IAppLogger log)
    {
        _mqtt = mqtt;
        _settings = settings;
        _state = state;
        _log = log;
    }

    public void Start(int periodMs)
    {
        if (IsRunning) return;

        if (periodMs < 200) periodMs = 200;

        _cts = new CancellationTokenSource();
        var ct = _cts.Token;

        _loop = Task.Run(async () =>
        {
            _log.Info($"Default worker started (period={periodMs}ms).");
            var rng = new Random();

            while (!ct.IsCancellationRequested)
            {
                try
                {
                    await EmitPowerAsync(rng, ct);
                    await EmitWaterAsync(rng, ct);
                    await EmitEnergyAsync(rng, ct);
                }
                catch (OperationCanceledException) { }
                catch (Exception ex)
                {
                    _log.Error("Default worker loop failed.", ex);
                }

                try { await Task.Delay(periodMs, ct); }
                catch (OperationCanceledException) { }
            }

            _log.Info("Default worker stopped.");
        }, ct);
    }

    public async Task StopAsync()
    {
        if (!IsRunning) return;

        try
        {
            _cts?.Cancel();
            if (_loop is not null)
                await _loop;
        }
        catch { /* ignore */ }
        finally
        {
            _cts?.Dispose();
            _cts = null;
            _loop = null;
        }
    }

    private IEnumerable<PowerKey> ResolvePowerKeys()
    {
        var (selected, overridden) = _state.SnapshotPower();

        IEnumerable<PowerKey> baseSet = selected.Count == 0 ? SensorCatalog.AllPowerKeys() : selected;
        return baseSet.Where(k => !overridden.Contains(k));
    }

    private IEnumerable<WaterKey> ResolveWaterKeys()
    {
        var (selected, overridden) = _state.SnapshotWater();

        IEnumerable<WaterKey> baseSet = selected.Count == 0 ? SensorCatalog.AllWaterKeys() : selected;
        return baseSet.Where(k => !overridden.Contains(k));
    }

    private IEnumerable<EnergyKey> ResolveEnergyKeys()
    {
        var (selected, overridden) = _state.SnapshotEnergy();

        IEnumerable<EnergyKey> baseSet = selected.Count == 0 ? SensorCatalog.AllEnergyKeys() : selected;
        return baseSet.Where(k => !overridden.Contains(k));
    }

    private async Task EmitPowerAsync(Random rng, CancellationToken ct)
    {
        foreach (var k in ResolvePowerKeys())
        {
            var inst = Math.Round(rng.NextDouble() * 30.0, 3);
            var acc = Math.Round(1000 + rng.NextDouble() * 5000.0, 3);

            var payload = new PowerPayload(k.Floor, k.Section, inst, acc, DateTime.Now);
            var topic = $"{_settings.BaseTopic}/power/F{k.Floor}{k.Section}";
            await _mqtt.PublishJsonAsync(topic, payload, ct);
        }
    }

    private async Task EmitWaterAsync(Random rng, CancellationToken ct)
    {
        foreach (var k in ResolveWaterKeys())
        {
            var inst = Math.Round(rng.NextDouble() * 3.0, 4);
            var acc = Math.Round(100 + rng.NextDouble() * 3000.0, 4);

            var payload = new WaterPayload(k.Floor, inst, acc, DateTime.Now);
            var topic = $"{_settings.BaseTopic}/water/F{k.Floor}";
            await _mqtt.PublishJsonAsync(topic, payload, ct);
        }
    }

    private async Task EmitEnergyAsync(Random rng, CancellationToken ct)
    {
        foreach (var k in ResolveEnergyKeys())
        {
            var v = Math.Round(rng.NextDouble() * 100.0, 3);
            var payload = new EnergyPayload(k.Floor, k.EnergyId, v, DateTime.Now);
            var topic = $"{_settings.BaseTopic}/energy/F{k.Floor}/{k.EnergyId}";
            await _mqtt.PublishJsonAsync(topic, payload, ct);
        }
    }
}
