using System.Text;

namespace SensorPublisher.Core;

public static class EnvConfigLoader
{
    /// <summary>
    /// Loads KEY=VALUE (optionally prefixed with 'export ') from a .env-style file.
    /// - Ignores blank lines and comments (# ...)
    /// - Removes surrounding single/double quotes
    /// - Returns a case-insensitive dictionary
    /// </summary>
    public static IReadOnlyDictionary<string, string> Load(string path)
    {
        var dict = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        if (!File.Exists(path))
            return dict;

        foreach (var raw in File.ReadAllLines(path, Encoding.UTF8))
        {
            var line = raw.Trim();
            if (string.IsNullOrWhiteSpace(line)) continue;
            if (line.StartsWith("#")) continue;

            if (line.StartsWith("export ", StringComparison.OrdinalIgnoreCase))
                line = line.Substring("export ".Length).Trim();

            var idx = line.IndexOf('=');
            if (idx <= 0) continue;

            var key = line.Substring(0, idx).Trim();
            var value = line.Substring(idx + 1).Trim();

            value = StripQuotes(value);

            if (!string.IsNullOrWhiteSpace(key))
                dict[key] = value;
        }

        return dict;
    }

    private static string StripQuotes(string value)
    {
        if (value.Length >= 2)
        {
            if ((value.StartsWith("\"") && value.EndsWith("\"")) ||
                (value.StartsWith("'") && value.EndsWith("'")))
            {
                return value.Substring(1, value.Length - 2);
            }
        }
        return value;
    }
}
