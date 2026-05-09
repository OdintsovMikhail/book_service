FROM python:3.12-slim-bookworm

# ── Install Microsoft ODBC Driver 18 ─────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
        -o /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 \
        mssql-tools18 \
        unixodbc-dev \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python dependencies ───────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application files ────────────────────────────────────────────────────
COPY utility.py schemas.py broker.py book_service.py ./

# ── Run ───────────────────────────────────────────────────────────────────────
EXPOSE 8000
CMD ["uvicorn", "book_service:app", "--host", "0.0.0.0", "--port", "8000"]