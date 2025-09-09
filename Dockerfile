FROM python:3.13
RUN useradd --create-home appuser

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV TZ="Europe/Moscow"

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && python -m pip install --no-cache-dir -r requirements.txt
COPY . ./
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD pgrep -f start.py || exit 1
CMD ["python", "start.py"]
