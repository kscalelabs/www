# Dockerfile
# Elastic Beanstalk Dockerfile using Python 3.11 and FastAPI

FROM python:3.11-slim

WORKDIR /app

ARG ENVIRONMENT
ARG COGNITO_AUTHORITY
ARG COGNITO_CLIENT_ID

ENV ENVIRONMENT=${ENVIRONMENT}}
ENV COGNITO_AUTHORITY=${COGNITO_AUTHORITY}
ENV COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID}

# Copy the requirements file first to leverage Docker's cache.
COPY /www/requirements.txt /app

# Installs Open3D dependencies.
RUN apt-get update && apt-get install -y \
    libglfw3 \
    libglfw3-dev \
    libgomp1

# Install Python dependencies.
RUN pip install \
    --no-cache-dir \
    --upgrade \
    -r requirements.txt

# Copy code and install Python dependencies.
COPY . /app

# Installs the project.
RUN pip install --no-cache-dir .

# Expose the port that the application runs on.
EXPOSE 8080

# Run the FastAPI application.
CMD ["fastapi", "run", "www/main.py", "--port", "8080"]
