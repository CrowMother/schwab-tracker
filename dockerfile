FROM python:3.11-slim

# Set the timezone environment variable (adjust to your desired timezone)
ENV TZ=America/New_York

# Install tzdata and set the timezone
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies, including git for pip installations from repositories
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Set working directory
WORKDIR /app

# Copy only necessary files
COPY . /app/


# Create volumes
VOLUME ["/app/logfile"]
VOLUME ["/app/order_data"]
VOLUME ["/app/database"]

# Expose necessary ports
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]
