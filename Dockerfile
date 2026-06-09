# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies required for dlib and sounddevice
RUN apt-get update && apt-get install -y build-essential cmake portaudio19-dev

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install python packages.
# Set CMAKE_BUILD_PARALLEL_LEVEL=1 to limit dlib compilation to a single core
# to prevent out-of-memory errors on platforms with limited resources.
RUN CMAKE_BUILD_PARALLEL_LEVEL=1 pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "agent.wsgi:application"]
