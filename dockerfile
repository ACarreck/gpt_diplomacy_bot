# Base Python image
FROM python:3.10-slim AS base

# Set up a working directory
WORKDIR /app

# Copy the Poetry lock files
COPY pyproject.toml poetry.lock ./

# Install Poetry
RUN pip install poetry

# Builder stage
FROM base AS builder

# Install dependencies
RUN poetry install --no-root

# Copy the source code
COPY . .

# Final runtime stage
FROM base

# Copy the installed packages from the builder stage
COPY --from=builder /root/.local /root/.local

# Set the environment variable to use local packages
ENV PATH=$PATH:/root/.local/bin

# Copy the source code
COPY . .

# Expose the Flask app port
EXPOSE 5000

# Start the Flask app and the bot
CMD ["sh", "-c", "python flask_oauth.py > flask_oauth.log 2>&1 & python diplomacy_bot.py > diplomacy_bot.log 2>&1 & wait"]
