FROM python:3.12.1-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./requirements.txt ./

RUN apt-get update && apt-get install -y curl unzip git

RUN pip install --no-cache-dir -r requirements.txt

# install aapt2
# https://dl.google.com/android/maven2/com/android/tools/build/aapt2/8.6.0-11315950/aapt2-8.6.0-11315950-linux.jar
RUN curl -L https://dl.google.com/android/maven2/com/android/tools/build/aapt2/8.6.0-11315950/aapt2-8.6.0-11315950-linux.jar -o /usr/local/bin/aapt2.jar
# unzip the jar, move the binary to /usr/local/bin
RUN mkdir -p /tmp/aapt2
RUN unzip /usr/local/bin/aapt2.jar -d /tmp/aapt2
RUN mv /tmp/aapt2/aapt2 /usr/local/bin/aapt2

# remove curl
RUN apt-get remove -y curl unzip
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
RUN rm -rf /tmp/aapt2

COPY ./ ./

ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION
ENV STORAGE_URL="osfs:///builds"

CMD ["uvicorn", "--host=0.0.0.0", "--port=8000", "app_distribution_server.app:app"]