using SensorPublisher.Core;

namespace SensorPublisher.WinForms;

public sealed class MainForm : Form
{
    private readonly LogHub _log = new();
    private readonly SelectionState _state = new();

    private IMqttPublisher? _mqtt;
    private MqttSettings? _settings;
    private DefaultDataWorker? _defaultWorker;

    private readonly ManualEmitSession _manualPower;
    private readonly ManualEmitSession _manualWater;
    private readonly ManualEmitSession _manualEnergy;

    // UI
    private SplitContainer _split = default!;
    private TabControl _tabs = default!;
    private TextBox _txtLog = default!;

    // Default tab controls
    private NumericUpDown _nudDefaultPeriod = default!;
    private Button _btnDefaultStart = default!;
    private Button _btnDefaultStop = default!;
    private Button _btnConnect = default!;
    private Label _lblConn = default!;

    // Manual Power controls
    private NumericUpDown _nudPowerPeriod = default!;
    private ComboBox _cbPowerFloor = default!;
    private ComboBox _cbPowerSection = default!;
    private CheckBox _chkPowerAll = default!;
    private Button _btnPowerStart = default!;
    private Button _btnPowerStop = default!;
    private Button _btnPowerOnce = default!;
    private Label _lblPowerCount = default!;

    // Manual Water controls
    private NumericUpDown _nudWaterPeriod = default!;
    private ComboBox _cbWaterFloor = default!;
    private CheckBox _chkWaterAll = default!;
    private Button _btnWaterStart = default!;
    private Button _btnWaterStop = default!;
    private Button _btnWaterOnce = default!;
    private Label _lblWaterCount = default!;

    // Manual Energy controls
    private NumericUpDown _nudEnergyPeriod = default!;
    private ComboBox _cbEnergyFloor = default!;
    private ComboBox _cbEnergyId = default!;
    private CheckBox _chkEnergyAll = default!;
    private Button _btnEnergyStart = default!;
    private Button _btnEnergyStop = default!;
    private Button _btnEnergyOnce = default!;
    private Label _lblEnergyCount = default!;

    public MainForm()
    {
        Text = "Sensor Publisher MVP (WinForms)";
        Width = 1200;
        Height = 720;
        StartPosition = FormStartPosition.CenterScreen;

        _manualPower = new ManualEmitSession(_log);
        _manualWater = new ManualEmitSession(_log);
        _manualEnergy = new ManualEmitSession(_log);

        BuildUi();
        HookLogging();

        Shown += async (_, __) =>
        {
            // Auto-load env + connect (best-effort)
            await InitializeCoreAsync();
        };

        FormClosing += async (_, __) =>
        {
            await SafeStopAllAsync();
            if (_mqtt is not null)
                await _mqtt.DisposeAsync();
        };
    }

    private void BuildUi()
    {
        _split = new SplitContainer
        {
            Dock = DockStyle.Fill,
            Orientation = Orientation.Vertical,
            SplitterDistance = 760
        };
        Controls.Add(_split);

        _tabs = new TabControl { Dock = DockStyle.Fill };
        _split.Panel1.Controls.Add(_tabs);

        _txtLog = new TextBox
        {
            Dock = DockStyle.Fill,
            Multiline = true,
            ReadOnly = true,
            ScrollBars = ScrollBars.Both,
            WordWrap = false
        };
        _split.Panel2.Controls.Add(_txtLog);

        // Tabs
        _tabs.TabPages.Add(BuildDefaultTab());
        _tabs.TabPages.Add(BuildPowerTab());
        _tabs.TabPages.Add(BuildWaterTab());
        _tabs.TabPages.Add(BuildEnergyTab());
    }

    private TabPage BuildDefaultTab()
    {
        var tab = new TabPage("Default");

        var panel = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            AutoScroll = true,
            Padding = new Padding(12)
        };
        tab.Controls.Add(panel);

        _btnConnect = new Button { Text = "Connect MQTT", Width = 160, Height = 32 };
        _btnConnect.Click += async (_, __) => await EnsureConnectedAsync();

        _lblConn = new Label { Text = "Status: (not connected)", AutoSize = true };

        _nudDefaultPeriod = new NumericUpDown
        {
            Minimum = 200,
            Maximum = 60_000,
            Value = 1000,
            Increment = 100,
            Width = 120
        };

        _btnDefaultStart = new Button { Text = "Start Default Worker", Width = 200, Height = 32 };
        _btnDefaultStop = new Button { Text = "Stop Default Worker", Width = 200, Height = 32, Enabled = false };

        _btnDefaultStart.Click += async (_, __) =>
        {
            try
            {
                await EnsureConnectedAsync();
                _defaultWorker ??= new DefaultDataWorker(_mqtt!, _settings!, _state, _log);
                _defaultWorker.Start((int)_nudDefaultPeriod.Value);
                _btnDefaultStart.Enabled = false;
                _btnDefaultStop.Enabled = true;
            }
            catch (Exception ex)
            {
                _log.Error("Failed to start default worker.", ex);
            }
        };

        _btnDefaultStop.Click += async (_, __) =>
        {
            if (_defaultWorker is null) return;
            await _defaultWorker.StopAsync();
            _btnDefaultStart.Enabled = true;
            _btnDefaultStop.Enabled = false;
        };

        // Basic default selection for MVP: allow all (empty set) vs a minimal curated set.
        var btnSelectAllDefaults = new Button { Text = "Default Select: Allow ALL (recommended)", Width = 320, Height = 32 };
        btnSelectAllDefaults.Click += (_, __) =>
        {
            _state.SetDefaultPower(Array.Empty<PowerKey>());
            _state.SetDefaultWater(Array.Empty<WaterKey>());
            _state.SetDefaultEnergy(Array.Empty<EnergyKey>());
            _log.Info("Default selection cleared => allow ALL.");
        };

        var btnSelectMinimal = new Button { Text = "Default Select: Minimal (F1 only)", Width = 320, Height = 32 };
        btnSelectMinimal.Click += (_, __) =>
        {
            _state.SetDefaultPower(new[] { new PowerKey(1, "A"), new PowerKey(1, "B") });
            _state.SetDefaultWater(new[] { new WaterKey(1) });
            _state.SetDefaultEnergy(SensorCatalog.EnergyIds.Select(id => new EnergyKey(1, id)));
            _log.Info("Default selection set => F1 only (MVP).");
        };

        panel.Controls.Add(_btnConnect);
        panel.Controls.Add(_lblConn);

        panel.Controls.Add(new Label { Text = "Default Period (ms):", AutoSize = true });
        panel.Controls.Add(_nudDefaultPeriod);

        panel.Controls.Add(_btnDefaultStart);
        panel.Controls.Add(_btnDefaultStop);

        panel.Controls.Add(new Label { Height = 12, AutoSize = false });
        panel.Controls.Add(btnSelectAllDefaults);
        panel.Controls.Add(btnSelectMinimal);

        panel.Controls.Add(new Label
        {
            Text = "Note: In MVP, default selection UI is simplified.\nManual sessions add keys to Override set, excluding them from default worker until stopped.",
            AutoSize = true
        });

        return tab;
    }

    private TabPage BuildPowerTab()
    {
        var tab = new TabPage("Power (Manual)");
        var panel = MakeManualPanel(tab);

        _nudPowerPeriod = MakePeriodNud(1000);
        _cbPowerFloor = MakeFloorCombo();
        _cbPowerSection = new ComboBox { Width = 80, DropDownStyle = ComboBoxStyle.DropDownList };
        _cbPowerSection.Items.AddRange(SensorCatalog.Sections.Cast<object>().ToArray());
        _cbPowerSection.SelectedIndex = 0;

        _chkPowerAll = new CheckBox { Text = "All Floors", AutoSize = true };
        _chkPowerAll.CheckedChanged += (_, __) =>
        {
            _cbPowerFloor.Enabled = !_chkPowerAll.Checked;
        };

        _btnPowerStart = new Button { Text = "Start", Width = 90, Height = 32 };
        _btnPowerStop = new Button { Text = "Stop", Width = 90, Height = 32, Enabled = false };
        _btnPowerOnce = new Button { Text = "Emit Once", Width = 110, Height = 32 };

        _lblPowerCount = new Label { Text = "Count: 0", AutoSize = true };

        _btnPowerOnce.Click += async (_, __) =>
        {
            try { await EnsureConnectedAsync(); await EmitPowerOnceAsync(CancellationToken.None); }
            catch (Exception ex) { _log.Error("Power emit once failed.", ex); }
        };

        _btnPowerStart.Click += async (_, __) =>
        {
            try
            {
                await EnsureConnectedAsync();
                ApplyPowerOverride(add: true);

                _manualPower.Start(
                    (int)_nudPowerPeriod.Value,
                    EmitPowerOnceAsync,
                    count => BeginInvoke(() => _lblPowerCount.Text = $"Count: {count}")
                );

                _btnPowerStart.Enabled = false;
                _btnPowerStop.Enabled = true;
            }
            catch (Exception ex)
            {
                _log.Error("Failed to start Power manual session.", ex);
            }
        };

        _btnPowerStop.Click += async (_, __) =>
        {
            await _manualPower.StopAsync();
            ApplyPowerOverride(add: false);
            _btnPowerStart.Enabled = true;
            _btnPowerStop.Enabled = false;
        };

        panel.Controls.Add(new Label { Text = "Period (ms):", AutoSize = true });
        panel.Controls.Add(_nudPowerPeriod);

        panel.Controls.Add(new Label { Text = "Floor:", AutoSize = true });
        panel.Controls.Add(_cbPowerFloor);
        panel.Controls.Add(_chkPowerAll);

        panel.Controls.Add(new Label { Text = "Section:", AutoSize = true });
        panel.Controls.Add(_cbPowerSection);

        panel.Controls.Add(_btnPowerStart);
        panel.Controls.Add(_btnPowerStop);
        panel.Controls.Add(_btnPowerOnce);
        panel.Controls.Add(_lblPowerCount);

        return tab;
    }

    private TabPage BuildWaterTab()
    {
        var tab = new TabPage("Water (Manual)");
        var panel = MakeManualPanel(tab);

        _nudWaterPeriod = MakePeriodNud(1000);
        _cbWaterFloor = MakeFloorCombo();
        _chkWaterAll = new CheckBox { Text = "All Floors", AutoSize = true };
        _chkWaterAll.CheckedChanged += (_, __) => _cbWaterFloor.Enabled = !_chkWaterAll.Checked;

        _btnWaterStart = new Button { Text = "Start", Width = 90, Height = 32 };
        _btnWaterStop = new Button { Text = "Stop", Width = 90, Height = 32, Enabled = false };
        _btnWaterOnce = new Button { Text = "Emit Once", Width = 110, Height = 32 };

        _lblWaterCount = new Label { Text = "Count: 0", AutoSize = true };

        _btnWaterOnce.Click += async (_, __) =>
        {
            try { await EnsureConnectedAsync(); await EmitWaterOnceAsync(CancellationToken.None); }
            catch (Exception ex) { _log.Error("Water emit once failed.", ex); }
        };

        _btnWaterStart.Click += async (_, __) =>
        {
            try
            {
                await EnsureConnectedAsync();
                ApplyWaterOverride(add: true);

                _manualWater.Start(
                    (int)_nudWaterPeriod.Value,
                    EmitWaterOnceAsync,
                    count => BeginInvoke(() => _lblWaterCount.Text = $"Count: {count}")
                );

                _btnWaterStart.Enabled = false;
                _btnWaterStop.Enabled = true;
            }
            catch (Exception ex)
            {
                _log.Error("Failed to start Water manual session.", ex);
            }
        };

        _btnWaterStop.Click += async (_, __) =>
        {
            await _manualWater.StopAsync();
            ApplyWaterOverride(add: false);
            _btnWaterStart.Enabled = true;
            _btnWaterStop.Enabled = false;
        };

        panel.Controls.Add(new Label { Text = "Period (ms):", AutoSize = true });
        panel.Controls.Add(_nudWaterPeriod);

        panel.Controls.Add(new Label { Text = "Floor:", AutoSize = true });
        panel.Controls.Add(_cbWaterFloor);
        panel.Controls.Add(_chkWaterAll);

        panel.Controls.Add(_btnWaterStart);
        panel.Controls.Add(_btnWaterStop);
        panel.Controls.Add(_btnWaterOnce);
        panel.Controls.Add(_lblWaterCount);

        return tab;
    }

    private TabPage BuildEnergyTab()
    {
        var tab = new TabPage("Energy (Manual)");
        var panel = MakeManualPanel(tab);

        _nudEnergyPeriod = MakePeriodNud(1000);
        _cbEnergyFloor = MakeFloorCombo();

        _cbEnergyId = new ComboBox { Width = 120, DropDownStyle = ComboBoxStyle.DropDownList };
        _cbEnergyId.Items.AddRange(SensorCatalog.EnergyIds.Cast<object>().ToArray());
        _cbEnergyId.SelectedIndex = 0;

        _chkEnergyAll = new CheckBox { Text = "All Floors", AutoSize = true };
        _chkEnergyAll.CheckedChanged += (_, __) => _cbEnergyFloor.Enabled = !_chkEnergyAll.Checked;

        _btnEnergyStart = new Button { Text = "Start", Width = 90, Height = 32 };
        _btnEnergyStop = new Button { Text = "Stop", Width = 90, Height = 32, Enabled = false };
        _btnEnergyOnce = new Button { Text = "Emit Once", Width = 110, Height = 32 };

        _lblEnergyCount = new Label { Text = "Count: 0", AutoSize = true };

        _btnEnergyOnce.Click += async (_, __) =>
        {
            try { await EnsureConnectedAsync(); await EmitEnergyOnceAsync(CancellationToken.None); }
            catch (Exception ex) { _log.Error("Energy emit once failed.", ex); }
        };

        _btnEnergyStart.Click += async (_, __) =>
        {
            try
            {
                await EnsureConnectedAsync();
                ApplyEnergyOverride(add: true);

                _manualEnergy.Start(
                    (int)_nudEnergyPeriod.Value,
                    EmitEnergyOnceAsync,
                    count => BeginInvoke(() => _lblEnergyCount.Text = $"Count: {count}")
                );

                _btnEnergyStart.Enabled = false;
                _btnEnergyStop.Enabled = true;
            }
            catch (Exception ex)
            {
                _log.Error("Failed to start Energy manual session.", ex);
            }
        };

        _btnEnergyStop.Click += async (_, __) =>
        {
            await _manualEnergy.StopAsync();
            ApplyEnergyOverride(add: false);
            _btnEnergyStart.Enabled = true;
            _btnEnergyStop.Enabled = false;
        };

        panel.Controls.Add(new Label { Text = "Period (ms):", AutoSize = true });
        panel.Controls.Add(_nudEnergyPeriod);

        panel.Controls.Add(new Label { Text = "Floor:", AutoSize = true });
        panel.Controls.Add(_cbEnergyFloor);
        panel.Controls.Add(_chkEnergyAll);

        panel.Controls.Add(new Label { Text = "Energy ID:", AutoSize = true });
        panel.Controls.Add(_cbEnergyId);

        panel.Controls.Add(_btnEnergyStart);
        panel.Controls.Add(_btnEnergyStop);
        panel.Controls.Add(_btnEnergyOnce);
        panel.Controls.Add(_lblEnergyCount);

        return tab;
    }

    private FlowLayoutPanel MakeManualPanel(TabPage tab)
    {
        var panel = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = true,
            AutoScroll = true,
            Padding = new Padding(12)
        };
        tab.Controls.Add(panel);
        return panel;
    }

    private NumericUpDown MakePeriodNud(int defaultMs)
        => new()
        {
            Minimum = 50,
            Maximum = 60_000,
            Value = defaultMs,
            Increment = 50,
            Width = 120
        };

    private ComboBox MakeFloorCombo()
    {
        var cb = new ComboBox { Width = 80, DropDownStyle = ComboBoxStyle.DropDownList };
        cb.Items.AddRange(SensorCatalog.Floors.Cast<object>().ToArray());
        cb.SelectedIndex = 0;
        return cb;
    }

    private void HookLogging()
    {
        _log.Line += line =>
        {
            if (IsDisposed) return;
            BeginInvoke(() =>
            {
                _txtLog.AppendText(line + Environment.NewLine);

                // keep last ~1000 lines
                var lines = _txtLog.Lines;
                if (lines.Length > 1000)
                {
                    _txtLog.Lines = lines.Skip(lines.Length - 800).ToArray();
                    _txtLog.SelectionStart = _txtLog.TextLength;
                    _txtLog.ScrollToCaret();
                }
            });
        };
    }

    private async Task InitializeCoreAsync()
    {
        try
        {
            var envPath = Path.Combine(AppContext.BaseDirectory, "config.env");
            var env = EnvConfigLoader.Load(envPath);
            _settings = MqttSettings.FromEnv(env);

            _log.Info($"Loaded config.env (found keys: {env.Count}). BaseTopic='{_settings.BaseTopic}' Host='{_settings.Host}:{_settings.Port}'");
            await EnsureConnectedAsync();
        }
        catch (Exception ex)
        {
            _log.Error("Initialization failed.", ex);
        }
    }

    private async Task EnsureConnectedAsync()
    {
        if (_settings is null)
        {
            var envPath = Path.Combine(AppContext.BaseDirectory, "config.env");
            var env = EnvConfigLoader.Load(envPath);
            _settings = MqttSettings.FromEnv(env);
        }

        if (_mqtt is null)
            _mqtt = new MqttPublisher(_settings!, _log);

        if (!_mqtt.IsConnected)
        {
            await _mqtt.ConnectAsync(CancellationToken.None);
        }

        _lblConn.Text = _mqtt.IsConnected
            ? $"Status: CONNECTED ({_settings!.Host}:{_settings!.Port})"
            : "Status: (not connected)";
    }

    private async Task SafeStopAllAsync()
    {
        try
        {
            if (_defaultWorker is not null) await _defaultWorker.StopAsync();
            await _manualPower.StopAsync();
            await _manualWater.StopAsync();
            await _manualEnergy.StopAsync();
        }
        catch { /* ignore */ }
    }

    // ----- Manual Emits (Power/Water/Energy) -----

    private IEnumerable<PowerKey> CurrentPowerKeys()
    {
        if (_chkPowerAll.Checked)
        {
            return SensorCatalog.AllPowerKeys().Where(k => k.Section == (string)_cbPowerSection.SelectedItem!);
        }
        else
        {
            var floor = (int)_cbPowerFloor.SelectedItem!;
            var section = (string)_cbPowerSection.SelectedItem!;
            return new[] { new PowerKey(floor, section) };
        }
    }

    private void ApplyPowerOverride(bool add)
    {
        var keys = CurrentPowerKeys();
        if (add) _state.AddOverridePower(keys);
        else _state.RemoveOverridePower(keys);
        _log.Info($"Power override {(add ? "ADDED" : "REMOVED")} ({keys.Count()} key(s)).");
    }

    private async Task EmitPowerOnceAsync(CancellationToken ct)
    {
        await EnsureConnectedAsync();
        var rng = new Random();

        foreach (var k in CurrentPowerKeys())
        {
            var inst = Math.Round(rng.NextDouble() * 30.0, 3);
            var acc = Math.Round(1000 + rng.NextDouble() * 5000.0, 3);
            var payload = new PowerPayload(k.Floor, k.Section, inst, acc, DateTime.Now);

            var topic = $"{_settings!.BaseTopic}/power/F{k.Floor}{k.Section}";
            await _mqtt!.PublishJsonAsync(topic, payload, ct);
        }
    }

    private IEnumerable<WaterKey> CurrentWaterKeys()
    {
        if (_chkWaterAll.Checked) return SensorCatalog.AllWaterKeys();
        var floor = (int)_cbWaterFloor.SelectedItem!;
        return new[] { new WaterKey(floor) };
    }

    private void ApplyWaterOverride(bool add)
    {
        var keys = CurrentWaterKeys();
        if (add) _state.AddOverrideWater(keys);
        else _state.RemoveOverrideWater(keys);
        _log.Info($"Water override {(add ? "ADDED" : "REMOVED")} ({keys.Count()} key(s)).");
    }

    private async Task EmitWaterOnceAsync(CancellationToken ct)
    {
        await EnsureConnectedAsync();
        var rng = new Random();

        foreach (var k in CurrentWaterKeys())
        {
            var inst = Math.Round(rng.NextDouble() * 3.0, 4);
            var acc = Math.Round(100 + rng.NextDouble() * 3000.0, 4);
            var payload = new WaterPayload(k.Floor, inst, acc, DateTime.Now);

            var topic = $"{_settings!.BaseTopic}/water/F{k.Floor}";
            await _mqtt!.PublishJsonAsync(topic, payload, ct);
        }
    }

    private IEnumerable<EnergyKey> CurrentEnergyKeys()
    {
        var energyId = (string)_cbEnergyId.SelectedItem!;
        if (_chkEnergyAll.Checked)
        {
            return SensorCatalog.Floors.Select(f => new EnergyKey(f, energyId));
        }
        else
        {
            var floor = (int)_cbEnergyFloor.SelectedItem!;
            return new[] { new EnergyKey(floor, energyId) };
        }
    }

    private void ApplyEnergyOverride(bool add)
    {
        var keys = CurrentEnergyKeys();
        if (add) _state.AddOverrideEnergy(keys);
        else _state.RemoveOverrideEnergy(keys);
        _log.Info($"Energy override {(add ? "ADDED" : "REMOVED")} ({keys.Count()} key(s)).");
    }

    private async Task EmitEnergyOnceAsync(CancellationToken ct)
    {
        await EnsureConnectedAsync();
        var rng = new Random();

        foreach (var k in CurrentEnergyKeys())
        {
            var v = Math.Round(rng.NextDouble() * 100.0, 3);
            var payload = new EnergyPayload(k.Floor, k.EnergyId, v, DateTime.Now);

            var topic = $"{_settings!.BaseTopic}/energy/F{k.Floor}/{k.EnergyId}";
            await _mqtt!.PublishJsonAsync(topic, payload, ct);
        }
    }
}
