# Dockerfile
FROM python:3.8-slim

WORKDIR /app

COPY VMM_Autoscaling.py /app
COPY requirements.txt /app

RUN pip install -r requirements.txt

CMD ["python", "VMM_Autoscaling.py"]
