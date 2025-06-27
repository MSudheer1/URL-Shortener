FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libncurses-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-cache

COPY . .

ENV PYTHONPATH=src
EXPOSE 8000

CMD ["uvicorn", "src.core.main:app", "--host", "0.0.0.0", "--port", "8000"]
