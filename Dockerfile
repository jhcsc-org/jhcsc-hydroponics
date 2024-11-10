FROM python:3.10-slim

WORKDIR /app

RUN apt-get update -o Acquire::Check-Valid-Until=false -o Acquire::AllowReleaseInfoChange=true && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY config/certs/ /app/config/certs/

ENV PYTHONUNBUFFERED=1

# Install Arduino CLI as root
RUN curl -L https://downloads.arduino.cc/arduino-cli/arduino-cli_1.0.4_Linux_64bit.tar.gz -o arduino-cli.tar.gz && \
    tar -xzf arduino-cli.tar.gz -C /usr/local/bin && \
    rm arduino-cli.tar.gz

# Create and switch to non-root user after installing Arduino CLI
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Copy the entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Set the default command to run the application
CMD ["python", "app.py"]