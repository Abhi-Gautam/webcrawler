# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app
# Copy the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY /scrapy.cfg ./
COPY /fetcher_service/ ./fetcher_service/

ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092
