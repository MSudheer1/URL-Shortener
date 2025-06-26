FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl build-essential

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root

COPY . .

ENV PYTHONPATH=src

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "src.core.main:app", "--host", "0.0.0.0", "--port", "8000"]
