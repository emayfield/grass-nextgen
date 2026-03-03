FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    fluidsynth \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create soundfonts directory
RUN mkdir -p soundfonts

# Download soundfont during build
RUN curl -L -o soundfonts/MuseScore_General.sf2 \
    https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2

# Expose port
EXPOSE 10000

# Run with gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
