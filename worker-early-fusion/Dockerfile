FROM python:3.11.6-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
  && update-ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean

COPY requirements.txt ./
RUN pip install --upgrade pip \
  && pip install -r requirements.txt

COPY app.py ./

EXPOSE 8095

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8095"]
