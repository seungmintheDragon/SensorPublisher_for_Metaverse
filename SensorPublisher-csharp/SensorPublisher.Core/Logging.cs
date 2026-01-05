namespace SensorPublisher.Core;

public interface IAppLogger
{
    void Info(string message);
    void Warn(string message);
    void Error(string message, Exception? ex = null);
}

/// <summary>
/// Minimal log hub. UI can subscribe to Lines to receive log lines.
/// Thread-safe and suitable for background tasks.
/// </summary>
public sealed class LogHub : IAppLogger
{
    private readonly object _lock = new();

    public event Action<string>? Line;

    public void Info(string message) => Publish("INFO", message);
    public void Warn(string message) => Publish("WARN", message);
    public void Error(string message, Exception? ex = null)
        => Publish("ERROR", ex is null ? message : $"{message} :: {ex.GetType().Name} {ex.Message}");

    private void Publish(string level, string message)
    {
        var ts = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
        var line = $"[{ts}] [{level}] {message}";
        Action<string>? handler;
        lock (_lock) handler = Line;
        handler?.Invoke(line);
    }
}
