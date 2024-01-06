FROM python:3.12.1-slim

WORKDIR /app

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ ./

ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION
ENV STORAGE_URL="osfs:///uploads"

CMD ["uvicorn", "--host=0.0.0.0", "--port=8000", "src.app:app"]

