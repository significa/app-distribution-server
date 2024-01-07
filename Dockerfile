FROM python:3.12.1-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ ./

ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION
ENV STORAGE_URL="osfs:///uploads"

CMD ["uvicorn", "--host=0.0.0.0", "--port=8000", "ipa_app_distribution_server.app:app"]

