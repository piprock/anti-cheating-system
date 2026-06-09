# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies required by sounddevice
RUN apt-get update && apt-get install -y portaudio19-dev

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "agent.wsgi:application"]
