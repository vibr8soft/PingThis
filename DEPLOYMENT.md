# PingThis Deployment Guide

This guide provides detailed instructions for deploying PingThis on various platforms.

## Quick Deploy Script

Save this as `deploy.sh` for rapid deployment:

```bash
#!/bin/bash
# PingThis Quick Deployment Script

set -e

echo "🚀 PingThis Quick Deploy"
echo "======================="

# Check Python version
python_version=$(python3 -V 2>&1 | grep -Po '(?<=Python )[0-9]+\.[0-9]+')
if ! python3 -c 'import sys; exit(1 if sys.version_info < (3, 8) else 0)'; then
    echo "❌ Python 3.8+ required. Found: $python_version"
    exit 1
fi
echo "✅ Python $python_version OK"

# Create virtual environment
echo "📦 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p config

# Copy config template if it doesn't exist
if [ ! -f "config/production.yaml" ]; then
    cp config/monitoring_config.yaml config/production.yaml
    echo "📝 Configuration template created at config/production.yaml"
    echo "   Please edit this file with your settings before running!"
else
    echo "📝 Using existing config/production.yaml"
fi

# Test installation
echo "🧪 Testing installation..."
if python -m src.main --config config/production.yaml --test-config; then
    echo "✅ Installation successful!"
    echo ""
    echo "Next steps:"
    echo "1. Edit config/production.yaml with your URLs and email settings"
    echo "2. Test: python -m src.main --config config/production.yaml --test-config"
    echo "3. Run: python -m src.main --config config/production.yaml"
else
    echo "⚠️  Installation complete but configuration needs setup"
    echo "   Edit config/production.yaml and run the test again"
fi
```

Make it executable:

```bash
chmod +x deploy.sh
./deploy.sh
```

## Platform-Specific Deployment

### Ubuntu/Debian Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3 python3-venv python3-pip git

# Create service user
sudo useradd -r -s /bin/false -m -d /opt/pingthis pingthis

# Deploy application
sudo -u pingthis bash << 'EOF'
cd /opt/pingthis
git clone <your-repo> . || { echo "Copy your files here manually"; }

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup configuration
cp config/monitoring_config.yaml config/production.yaml
chmod 600 config/production.yaml  # Protect email credentials
EOF

# Create systemd service
sudo tee /etc/systemd/system/pingthis.service > /dev/null << EOF
[Unit]
Description=PingThis Website Monitor
Documentation=https://github.com/your-repo
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pingthis
Group=pingthis
WorkingDirectory=/opt/pingthis
Environment=PATH=/opt/pingthis/venv/bin
ExecStart=/opt/pingthis/venv/bin/python -m src.main --config config/production.yaml
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=60
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pingthis

# Security settings
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/pingthis/logs
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl daemon-reload
sudo systemctl enable pingthis

# Edit configuration before starting
echo "Edit /opt/pingthis/config/production.yaml then start with:"
echo "sudo systemctl start pingthis"
echo "sudo systemctl status pingthis"
```

### CentOS/RHEL/Rocky Linux

```bash
# Install Python and dependencies
sudo dnf install -y python3 python3-pip git

# Follow Ubuntu steps above, but use dnf instead of apt
```

### Windows Server

```powershell
# Install Python 3.8+ from python.org
# Then in PowerShell:

# Clone or copy files
cd C:\
mkdir PingThis
cd PingThis
# Copy your files here

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration
copy config\monitoring_config.yaml config\production.yaml

# Test
python -m src.main --config config\production.yaml --test-config

# Install as Windows service using NSSM (Non-Sucking Service Manager)
# Download NSSM from nssm.cc
nssm install PingThis C:\PingThis\venv\Scripts\python.exe
nssm set PingThis Arguments "-m src.main --config config\production.yaml"
nssm set PingThis AppDirectory C:\PingThis
nssm start PingThis
```

### Docker Deployment

#### Basic Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ src/
COPY config/ config/

# Create logs directory
RUN mkdir -p logs

# Run as non-root user
RUN useradd -m -u 1001 pingthis
USER pingthis

# Health check
HEALTHCHECK --interval=5m --timeout=30s --start-period=1m \
  CMD python -m src.main --config config/monitoring_config.yaml --status || exit 1

# Run application
CMD ["python", "-m", "src.main", "--config", "config/monitoring_config.yaml"]
```

```bash
# Build and run
docker build -t pingthis .
docker run -d \
  --name pingthis \
  --restart unless-stopped \
  -v $(pwd)/config/production.yaml:/app/config/monitoring_config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  pingthis
```

#### Docker Compose

```yaml
# docker-compose.yml
version: "3.8"

services:
  pingthis:
    build: .
    container_name: pingthis
    restart: unless-stopped
    volumes:
      - ./config/production.yaml:/app/config/monitoring_config.yaml:ro
      - ./logs:/app/logs
    environment:
      - TZ=UTC
    healthcheck:
      test: ["CMD", "python", "-m", "src.main", "--status"]
      interval: 5m
      timeout: 30s
      retries: 3
      start_period: 1m
```

```bash
# Deploy with Docker Compose
docker-compose up -d
docker-compose logs -f
```

### Kubernetes Deployment

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pingthis
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: pingthis
  template:
    metadata:
      labels:
        app: pingthis
    spec:
      containers:
        - name: pingthis
          image: pingthis:latest
          volumeMounts:
            - name: config
              mountPath: /app/config/monitoring_config.yaml
              subPath: monitoring_config.yaml
              readOnly: true
            - name: logs
              mountPath: /app/logs
          resources:
            limits:
              memory: "256Mi"
              cpu: "200m"
            requests:
              memory: "128Mi"
              cpu: "100m"
          livenessProbe:
            exec:
              command:
                - python
                - -m
                - src.main
                - --status
            initialDelaySeconds: 60
            periodSeconds: 300
      volumes:
        - name: config
          configMap:
            name: pingthis-config
        - name: logs
          persistentVolumeClaim:
            claimName: pingthis-logs

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: pingthis-config
  namespace: monitoring
data:
  monitoring_config.yaml: |
    # Your configuration here
    log_level: "INFO"
    # ... rest of config

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pingthis-logs
  namespace: monitoring
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

## Configuration Management

### Environment Variables

PingThis can use environment variables for sensitive data:

```yaml
# config/production.yaml
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  username: "${EMAIL_USERNAME}"
  password: "${EMAIL_PASSWORD}"
  from_email: "${EMAIL_FROM}"
  to_emails:
    - "${EMAIL_TO}"
```

```bash
# Set environment variables
export EMAIL_USERNAME="your_email@gmail.com"
export EMAIL_PASSWORD="your_app_password"
export EMAIL_FROM="your_email@gmail.com"
export EMAIL_TO="alerts@yourcompany.com"
```

### Multiple Environments

```bash
# Development
python -m src.main --config config/dev.yaml

# Staging
python -m src.main --config config/staging.yaml

# Production
python -m src.main --config config/production.yaml
```

## Monitoring the Monitor

### Health Checks

```bash
#!/bin/bash
# healthcheck.sh

# Check if PingThis is running
if ! pgrep -f "src.main" > /dev/null; then
    echo "❌ PingThis is not running"
    exit 1
fi

# Check recent logs
if ! tail -n 10 logs/pingthis.log | grep -q "$(date +%Y-%m-%d)"; then
    echo "❌ No recent log entries"
    exit 1
fi

echo "✅ PingThis is healthy"
exit 0
```

### Log Rotation

```bash
# /etc/logrotate.d/pingthis
/opt/pingthis/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

### Monitoring with Nagios/Icinga

```bash
#!/usr/bin/env python3
# check_pingthis.py - Nagios plugin

import sys
import subprocess
import json

def main():
    try:
        result = subprocess.run([
            'python', '-m', 'src.main', '--status'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            print("CRITICAL - PingThis not responding")
            sys.exit(2)

        # Parse status output
        # Add your logic here to check the status

        print("OK - PingThis is running normally")
        sys.exit(0)

    except Exception as e:
        print(f"UNKNOWN - Error checking PingThis: {e}")
        sys.exit(3)

if __name__ == '__main__':
    main()
```

## Security Considerations

### File Permissions

```bash
# Secure configuration files
chmod 600 config/*.yaml
chown pingthis:pingthis config/*.yaml

# Secure log directory
chmod 755 logs/
chown pingthis:pingthis logs/
```

### Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow out 587/tcp  # SMTP TLS
sudo ufw allow out 25/tcp   # SMTP
sudo ufw allow out 80/tcp   # HTTP
sudo ufw allow out 443/tcp  # HTTPS

# iptables
iptables -A OUTPUT -p tcp --dport 587 -j ACCEPT  # SMTP TLS
iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT   # HTTP
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT  # HTTPS
```

### App Passwords

For Gmail and other providers:

1. Enable 2-Factor Authentication
2. Generate an App Password
3. Use the App Password in configuration
4. Never commit passwords to version control

### Network Security

- Use TLS/SSL for SMTP
- Monitor only HTTPS URLs when possible
- Consider using a VPN for sensitive monitoring
- Implement proper DNS security

## Performance Tuning

### Large Scale Monitoring

For monitoring many URLs:

```yaml
# Increase check intervals
check_interval: 600 # 10 minutes

# Stagger checks by using different intervals
monitors:
  - url: "https://critical-site.com"
    check_interval: 120 # 2 minutes
  - url: "https://normal-site.com"
    check_interval: 300 # 5 minutes
  - url: "https://low-priority.com"
    check_interval: 900 # 15 minutes
```

### Resource Limits

```bash
# Systemd service limits
[Service]
MemoryMax=256M
CPUQuota=20%
TasksMax=50
```

### Database Backend (Advanced)

For very large deployments, consider implementing a database backend instead of JSON file storage.

## Troubleshooting Deployment

### Common Issues

1. **Permission denied errors**:

   ```bash
   sudo chown -R pingthis:pingthis /opt/pingthis
   sudo chmod -R 755 /opt/pingthis
   sudo chmod 600 /opt/pingthis/config/*.yaml
   ```

2. **Python module not found**:

   ```bash
   # Ensure virtual environment is activated
   source venv/bin/activate
   which python  # Should point to venv/bin/python
   ```

3. **SMTP authentication failures**:

   - Use App Passwords for Gmail
   - Check firewall allows outbound SMTP
   - Verify credentials with manual SMTP test

4. **SSL certificate errors**:
   ```bash
   # Update CA certificates
   sudo apt update && sudo apt install ca-certificates
   ```

### Log Analysis

```bash
# Monitor logs in real-time
tail -f logs/pingthis.log

# Check for errors
grep -i error logs/pingthis.log

# Check email sending
grep "EMAIL SENT" logs/pingthis.log

# Check state changes
grep "STATE CHANGE" logs/pingthis.log
```

## Backup and Recovery

### Backup Script

```bash
#!/bin/bash
# backup_pingthis.sh

BACKUP_DIR="/backups/pingthis"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" config/

# Backup state and logs
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" logs/

# Keep only last 30 days of backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR"
```

### Recovery Process

1. Stop the service
2. Restore configuration and data
3. Test configuration
4. Start the service

```bash
# Stop service
sudo systemctl stop pingthis

# Restore from backup
cd /opt/pingthis
tar -xzf /backups/pingthis/config_YYYYMMDD_HHMMSS.tar.gz
tar -xzf /backups/pingthis/data_YYYYMMDD_HHMMSS.tar.gz

# Test and start
python -m src.main --test-config
sudo systemctl start pingthis
```

This deployment guide should help you get PingThis running in any environment. Remember to always test your configuration before going live!
