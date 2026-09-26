FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Read runtime dependencies from the project's existing source of truth.
COPY pyproject.toml ./
RUN python -c "import subprocess, sys, tomllib; dependencies = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *dependencies])"

COPY app/ ./app/
COPY test_data/ ./test_data/
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Fail the build if the API or its runtime dependencies cannot be imported.
RUN python -c "from app.main import app; assert app is not None"

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --no-create-home \
       --shell /usr/sbin/nologin appuser

USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

