FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libxrender1 libxtst6 libxi6 libatk1.0-0 \
    libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy app files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Cloud Run expects
EXPOSE 8080

# Run the app
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
