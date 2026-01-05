namespace SensorPublisher.Core;

// Keep payloads flexible for MVP. Replace with your exact schema later.

public sealed record PowerPayload(
    int Floor,
    string Section,
    double InstKw,
    double AccKwh,
    DateTime Timestamp
);

public sealed record WaterPayload(
    int Floor,
    double InstFlow,
    double AccFlow,
    DateTime Timestamp
);

public sealed record EnergyPayload(
    int Floor,
    string EnergyId,
    double Value,
    DateTime Timestamp
);
