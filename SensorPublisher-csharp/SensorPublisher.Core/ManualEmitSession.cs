namespace SensorPublisher.Core;

/// <summary>
/// A reusable periodic emitter with Start/Stop and count callback.
/// Intended to be driven by UI (per tab).
/// </summary>
public sealed class ManualEmitSession
{
    private readonly IAppLogger _log;
    private CancellationTokenSource? _cts;
    private Task? _loop;
    private int _count;

    public bool IsRunning => _cts is not null && !_cts.IsCancellationRequested;

    public ManualEmitSession(IAppLogger log)
    {
        _log = log;
    }

    public void Start(int periodMs, Func<CancellationToken, Task> emitOnceAsync, Action<int>? onCount = null)
    {
        if (IsRunning) return;

        if (periodMs < 50) periodMs = 50;

        _cts = new CancellationTokenSource();
        var ct = _cts.Token;
        _count = 0;

        _loop = Task.Run(async () =>
        {
            _log.Info($"Manual session started (period={periodMs}ms).");
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    await emitOnceAsync(ct);
                    _count++;
                    onCount?.Invoke(_count);
                }
                catch (OperationCanceledException) { }
                catch (Exception ex)
                {
                    _log.Error("Manual session emit failed.", ex);
                }

                try
                {
                    await Task.Delay(periodMs, ct);
                }
                catch (OperationCanceledException) { }
            }
            _log.Info("Manual session stopped.");
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
}
