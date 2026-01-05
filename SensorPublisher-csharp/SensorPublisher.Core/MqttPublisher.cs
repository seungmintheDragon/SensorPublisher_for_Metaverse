using MQTTnet;
using MQTTnet.Client;
using MQTTnet.Formatter;
using MQTTnet.Protocol;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;

namespace SensorPublisher.Core;

public interface IMqttPublisher : IAsyncDisposable
{
    Task ConnectAsync(CancellationToken ct);
    Task PublishJsonAsync(string topic, object payload, CancellationToken ct);
    bool IsConnected { get; }
}

public sealed class MqttPublisher : IMqttPublisher
{
    private readonly IAppLogger _log;
    private readonly MqttSettings _settings;

    private readonly IMqttClient _client;
    private readonly MqttClientOptions _options; // v4: IMqttClientOptions -> MqttClientOptions

    public bool IsConnected => _client.IsConnected;

    public MqttPublisher(MqttSettings settings, IAppLogger log)
    {
        _settings = settings;
        _log = log;

        var factory = new MqttFactory();
        _client = factory.CreateMqttClient();

        _client.DisconnectedAsync += args =>
        {
            _log.Warn($"MQTT disconnected. Reason: {args.Reason}");
            return Task.CompletedTask;
        };

        _client.ConnectedAsync += args =>
        {
            _log.Info("MQTT connected.");
            return Task.CompletedTask;
        };

        var builder = new MqttClientOptionsBuilder()
            .WithClientId(settings.ClientId)
            .WithTcpServer(settings.Host, settings.Port)
            .WithCleanSession();

        if (!string.IsNullOrWhiteSpace(settings.Username))
            builder = builder.WithCredentials(settings.Username, settings.Password);

        if (settings.UseTls)
        {
            var tls = new MqttClientOptionsBuilderTlsParameters
            {
                UseTls = true,
                IgnoreCertificateChainErrors = settings.IgnoreCertChainErrors,
                IgnoreCertificateRevocationErrors = settings.IgnoreCertRevocationErrors,
                AllowUntrustedCertificates = settings.AllowUntrustedCertificates
            };

            if (!string.IsNullOrWhiteSpace(settings.CaCertPath) && File.Exists(settings.CaCertPath))
            {
                try
                {
                    // v4: Certificates´Â IEnumerable<X509Certificate>
                    var ca = new X509Certificate2(settings.CaCertPath);
                    tls.Certificates = new List<X509Certificate> { ca };

                    _log.Info($"Loaded CA cert: {settings.CaCertPath}");
                }
                catch (Exception ex)
                {
                    _log.Warn($"Failed to load CA cert '{settings.CaCertPath}'. Proceeding without it. {ex.Message}");
                }
            }

            builder = builder.WithTls(tls);
        }

        _options = builder
            .WithProtocolVersion(MqttProtocolVersion.V500)
            .Build();
    }

    public async Task ConnectAsync(CancellationToken ct)
    {
        if (_client.IsConnected) return;

        _log.Info($"Connecting MQTT {_settings.Host}:{_settings.Port} TLS={_settings.UseTls}");
        await _client.ConnectAsync(_options, ct);
    }

    public async Task PublishJsonAsync(string topic, object payload, CancellationToken ct)
    {
        if (!_client.IsConnected)
            throw new InvalidOperationException("MQTT client is not connected.");

        var json = JsonSerializer.Serialize(payload);

        var msg = new MqttApplicationMessageBuilder()
            .WithTopic(topic)
            .WithPayload(Encoding.UTF8.GetBytes(json))
            .WithQualityOfServiceLevel(_settings.Qos)
            .WithRetainFlag(_settings.Retain)
            .Build();

        await _client.PublishAsync(msg, ct);
    }

    public async ValueTask DisposeAsync()
    {
        try
        {
            if (_client.IsConnected)
                await _client.DisconnectAsync();
        }
        catch { /* ignore */ }

        _client.Dispose();
    }
}

public sealed class MqttSettings
{
    public string Host { get; init; } = "localhost";
    public int Port { get; init; } = 1883;
    public string ClientId { get; init; } = $"SensorPublisher-{Guid.NewGuid():N}";
    public string? Username { get; init; }
    public string? Password { get; init; }

    public string BaseTopic { get; init; } = "building";
    public MqttQualityOfServiceLevel Qos { get; init; } = MqttQualityOfServiceLevel.AtLeastOnce;
    public bool Retain { get; init; } = false;

    public bool UseTls { get; init; } = false;
    public string? CaCertPath { get; init; }

    public bool AllowUntrustedCertificates { get; init; } = false;
    public bool IgnoreCertChainErrors { get; init; } = false;
    public bool IgnoreCertRevocationErrors { get; init; } = false;

    public static MqttSettings FromEnv(IReadOnlyDictionary<string, string> env)
    {
        var host = env.TryGetValue("MQTT_HOST", out var h) ? h : "localhost";
        var port = env.TryGetValue("MQTT_PORT", out var p) && int.TryParse(p, out var pi) ? pi : 1883;
        var user = env.TryGetValue("MQTT_USER", out var u) ? u : null;
        var pass = env.TryGetValue("MQTT_PASS", out var pw) ? pw : null;
        var ca = env.TryGetValue("MQTT_CA_CERT", out var caPath) ? caPath : null;

        var baseTopic = env.TryGetValue("MQTT_BASE_TOPIC", out var bt) ? bt : "building";
        var qos = env.TryGetValue("MQTT_QOS", out var q) && int.TryParse(q, out var qi)
            ? (MqttQualityOfServiceLevel)Math.Clamp(qi, 0, 2)
            : MqttQualityOfServiceLevel.AtLeastOnce;
        var retain = env.TryGetValue("MQTT_RETAIN", out var r) && bool.TryParse(r, out var rb) ? rb : false;

        var useTls = port == 8883 || !string.IsNullOrWhiteSpace(ca);

        return new MqttSettings
        {
            Host = host,
            Port = port,
            Username = user,
            Password = pass,
            CaCertPath = ca,
            BaseTopic = baseTopic,
            Qos = qos,
            Retain = retain,
            UseTls = useTls
        };
    }
}
