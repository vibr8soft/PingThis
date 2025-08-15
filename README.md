# PingThis - Website Monitoring System

A clean architecture Python application for monitoring website uptime with email alerts.

## Features

- 🔍 **Website Monitoring**: Continuously monitor multiple websites/APIs
- 📧 **Smart Alerts**: Email notifications for downtime and recovery
- 🚫 **No Spam**: Only sends one alert per downtime, prevents email spam
- 📊 **Comprehensive Logging**: Detailed logs of all ping attempts and state changes
- ⚙️ **Flexible Configuration**: YAML-based configuration with per-URL settings
- 🏗️ **Clean Architecture**: Well-structured, maintainable codebase
- 🐍 **Virtual Environment Ready**: Easy deployment on any server

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository (if using git)
git clone <your-repo-url>
cd PingThis

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Monitoring

Copy and edit the configuration file:

```bash
cp config/monitoring_config.yaml config/my_config.yaml
# Edit config/my_config.yaml with your URLs and email settings
```

### 3. Run the Application

```bash
# Test configuration
python -m src.main --config config/my_config.yaml --test-config

# Start monitoring
python -m src.main --config config/my_config.yaml
```

## Configuration

Edit `config/monitoring_config.yaml` with your settings:

```yaml
# Email settings
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  username: "your_email@gmail.com"
  password: "your_app_password" # Use App Password for Gmail
  from_email: "your_email@gmail.com"
  to_emails:
    - "alerts@yourcompany.com"

# URLs to monitor
monitors:
  - url: "https://yourwebsite.com"
    timeout: 30
    check_interval: 300 # 5 minutes
  - url: "https://api.yourservice.com/health"
    timeout: 15
    check_interval: 180 # 3 minutes
```

### Gmail Setup

For Gmail, you need to:

1. Enable 2-Factor Authentication
2. Generate an App Password
3. Use the App Password in the configuration

## Usage

### Basic Commands

```bash
# Test configuration and email setup
python -m src.main --test-config

# Show current status
python -m src.main --status

# Send summary report
python -m src.main --send-report

# Start monitoring (runs continuously)
python -m src.main
```

### Advanced Usage

```bash
# Use custom config file
python -m src.main --config /path/to/config.yaml

# Run in background (Linux/macOS)
nohup python -m src.main --config config/my_config.yaml > pingthis.out 2>&1 &

# Run as systemd service (Linux)
# See deployment section below
```

## How It Works

### Alert Logic

PingThis implements smart alerting to prevent spam:

1. **Down Alert**: Sent only when:

   - Previous ping was successful (UP)
   - Current ping fails (DOWN)
   - No down alert has been sent for this downtime

2. **Recovery Alert**: Sent only when:

   - Previous state was DOWN
   - Current ping succeeds (UP)
   - A down alert was previously sent

3. **State Persistence**: States are saved to prevent duplicate alerts across restarts

### Monitoring Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Config    │    │    Ping     │    │   State     │    │    Email    │
│  Manager    │───▶│   Checker   │───▶│  Manager    │───▶│  Notifier   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
Load URLs &         Send HTTP           Track UP/DOWN        Send alerts
email settings      requests            state changes       via SMTP
```

## Deployment

### Linux Systemd Service

Create `/etc/systemd/system/pingthis.service`:

```ini
[Unit]
Description=PingThis Website Monitor
After=network.target

[Service]
Type=simple
User=monitoring
Group=monitoring
WorkingDirectory=/opt/pingthis
ExecStart=/opt/pingthis/venv/bin/python -m src.main --config config/production.yaml
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pingthis
sudo systemctl start pingthis
sudo systemctl status pingthis
```

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY config/ config/

CMD ["python", "-m", "src.main", "--config", "config/monitoring_config.yaml"]
```

Build and run:

```bash
docker build -t pingthis .
docker run -d --name pingthis -v $(pwd)/config:/app/config -v $(pwd)/logs:/app/logs pingthis
```

### Server Setup Script

```bash
#!/bin/bash
# setup.sh - Quick server setup script

# Create user and directories
sudo useradd -m -s /bin/bash monitoring
sudo mkdir -p /opt/pingthis
sudo chown monitoring:monitoring /opt/pingthis

# Switch to monitoring user
sudo -u monitoring bash << 'EOF'
cd /opt/pingthis

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# Install application (adjust path as needed)
pip install -r requirements.txt

# Copy configuration template
cp config/monitoring_config.yaml config/production.yaml
echo "Edit /opt/pingthis/config/production.yaml with your settings"
EOF

echo "Setup complete! Edit configuration and start the service."
```

## File Structure

```
PingThis/
├── src/                          # Source code
│   ├── config/                   # Configuration management
│   │   └── config_manager.py
│   ├── monitoring/               # Core monitoring logic
│   │   ├── ping_checker.py
│   │   └── state_manager.py
│   ├── notifications/            # Email system
│   │   └── email_notifier.py
│   ├── utils/                    # Utilities
│   │   └── logger.py
│   └── main.py                   # Main application
├── config/                       # Configuration files
│   └── monitoring_config.yaml
├── logs/                         # Log files (created automatically)
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
└── README.md                     # This file
```

## Configuration Reference

### Global Settings

| Setting          | Description                                               | Default           |
| ---------------- | --------------------------------------------------------- | ----------------- |
| `log_level`      | Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL) | INFO              |
| `log_file`       | Path to log file                                          | logs/pingthis.log |
| `check_interval` | Default check interval in seconds                         | 300               |

### Email Settings

| Setting       | Description              | Required           |
| ------------- | ------------------------ | ------------------ |
| `smtp_server` | SMTP server hostname     | Yes                |
| `smtp_port`   | SMTP server port         | Yes                |
| `username`    | SMTP username            | Yes                |
| `password`    | SMTP password            | Yes                |
| `from_email`  | From email address       | Yes                |
| `to_emails`   | List of recipient emails | Yes                |
| `use_tls`     | Use TLS encryption       | No (default: true) |

### Monitor Settings

| Setting                 | Description                   | Default              |
| ----------------------- | ----------------------------- | -------------------- |
| `url`                   | URL to monitor                | Required             |
| `timeout`               | Request timeout in seconds    | 30                   |
| `check_interval`        | Check interval in seconds     | Global default       |
| `expected_status_codes` | List of acceptable HTTP codes | [200, 201, 202, 204] |

## Logging

Logs are written to both file and console with different detail levels:

- **File**: Detailed logs including function names and line numbers
- **Console**: Clean, readable logs for monitoring

Log levels:

- **DEBUG**: Detailed debugging information
- **INFO**: General information about operations
- **WARNING**: Important events (state changes)
- **ERROR**: Error conditions
- **CRITICAL**: Critical errors that may stop the application

## Troubleshooting

### Common Issues

1. **Email not sending**:

   ```bash
   # Test email configuration
   python -m src.main --test-config
   ```

2. **Permission denied on log files**:

   ```bash
   # Create logs directory with proper permissions
   mkdir -p logs
   chmod 755 logs
   ```

3. **SSL certificate errors**:

   - Check if the URL uses valid SSL certificates
   - For self-signed certificates, consider using HTTP instead

4. **High memory usage**:
   - Reduce the number of concurrent monitors
   - Increase check intervals

### Debug Mode

Run with debug logging:

```yaml
# In config file
log_level: "DEBUG"
```

Or check logs:

```bash
tail -f logs/pingthis.log
```

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- Check the logs for detailed error information
- Ensure your configuration file is valid YAML
- Test email settings with `--test-config`
- For deployment issues, check system logs
