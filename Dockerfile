FROM python:3.13-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIPENV_VENV_IN_PROJECT=1
ENV PIPENV_IGNORE_VIRTUALENVS=1

RUN pip install --upgrade pip

RUN apt-get update \
    && apt-get -y install gcc \
    && pip install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --system

COPY . .

# Collect static files during build
RUN python manage.py collectstatic --noinput

EXPOSE 8000
RUN chmod +x /app/entrypoint.prod.sh
CMD ["/app/entrypoint.prod.sh"]