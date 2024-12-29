# Getting Started

To get started, clone the repository and check out the [Project Tracker](https://github.com/orgs/kscalelabs/projects/8/views/1).

You can contribute to the K-Scale WWW project in various ways, such as reporting bugs, submitting pull requests, raising issues, or creating suggestions.

> [!IMPORTANT]
> You **MUST** access the locally run website through `127.0.0.1:3000` and **NOT** `localhost:3000`. This is because the CORS policy is configured to only allow requests from the exact domain `127.0.0.1:3000`.

> [!NOTE]
> You should develop the backend using Python 3.11 or later

---

# Development

1. [Development Setup](#development-setup)
   - [Configuration](#configuration)
   - [Google OAuth Configuration](#google-oauth-configuration)
   - [GitHub OAuth Configuration](#github-oauth-configuration)
2. [Database Setup](#database-setup)
   - [DynamoDB/S3](#dynamodbs3)
   - [Admin Panel](#admin-panel)
3. [FastAPI Setup](#fastapi-setup)
   - [Creating a Python Virtual Environment](#creating-a-python-virtual-environment)
   - [Installing Project Dependencies](#installing-project-dependencies)
   - [Initializing the Test Databases](#initializing-the-test-databases)
   - [Running the FastAPI Application](#running-the-fastapi-application)
4. [Syncing Frontend and Backend](#syncing-frontend-and-backend)
5. [React Setup](#react-setup)
6. [Testing](#testing)

---

## Development Setup

### Configuration

Backend settings are located in the `www/settings/` directory. You can specify which settings to use by setting the `ENVIRONMENT` variable to the corresponding config file stem in `www/settings/configs/`. For local development, this should typically be set to `local`.

Place the required environment variables in `env.sh` or `.env.local`.

To run the server or tests locally, source the environment variables in each new terminal session:

```bash
source env.sh  # or source .env.local
```

**Example `env.sh`/`.env.local` file:**

```bash
# Specifies a local environment versus production environment.
export ENVIRONMENT=local

# For AWS
export AWS_DEFAULT_REGION='us-east-1'
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_ENDPOINT_URL_S3='http://127.0.0.1:4566'
export AWS_ENDPOINT_URL_DYNAMODB='http://127.0.0.1:4566'

# For letting the frontend know the backend URL.
export VITE_APP_BACKEND_URL='http://127.0.0.1:8080'

# For SMTP
export SMTP_HOST='smtp.gmail.com'
export SMTP_SENDER_EMAIL=''
export SMTP_PASSWORD=''
export SMTP_SENDER_NAME=''
export SMTP_USERNAME=''

# For Github OAuth
export GITHUB_CLIENT_ID=''
export GITHUB_CLIENT_SECRET=''

# For Google OAuth
export VITE_GOOGLE_CLIENT_ID=''

# For OnShape
export ONSHAPE_ACCESS_KEY=''
export ONSHAPE_SECRET_KEY=''
```

### Google OAuth Configuration

The repository's local configuration comes with Google OAuth credentials for a test application. Alternatively, you can set up your own Google OAuth application to test the application locally, by following the instructions [here](https://blog.logrocket.com/guide-adding-google-login-react-app/).

### Github OAuth Configuration

The repository's local configuration comes with Github OAuth credentials for a test application. Alternatively, you can set up your own Github OAuth application to test the application locally:

1. Create an OAuth App on [Github Developer Settings](https://github.com/settings/developers)
2. Set both Homepage URL and Authorization callback URL to `http://127.0.0.1:3000/login` before you `Update application` on Github Oauth App configuration
3. Copy the Client ID and Client Secret from Github OAuth App configuration and set them in `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` respectively

## Database Setup

### DynamoDB/S3

For local development, install the `AWS CLI` and use the `localstack/localstack` Docker image to run a local AWS instance:

```bash
docker pull localstack/localstack  # If you haven't already
docker run -d --name localstack -p 4566:4566 -p 4571:4571 localstack/localstack
```

Then, if you need to kill the database, you can run:

```bash
docker kill localstack || true
docker rm localstack || true
```

Initialize the artifact bucket with:

```bash
aws s3api create-bucket --bucket artifacts
```

#### Admin Panel

DynamoDB Admin provides a GUI for viewing your tables and their entries. To install, run:

```bash
npm i -g dynamodb-admin
```

To launch DynamoDB Admin, **source the environment variables used for FastAPI**, then run:

```bash
DYNAMO_ENDPOINT=http://127.0.0.1:4566 dynamodb-admin
```

## FastAPI Setup

### Creating a Python Virtual Environment

Create a Python virtual environment using [uv](https://astral.sh/blog/uv) or [virtualenv](https://virtualenv.pypa.io/en/latest/) with **Python 3.11 or later**:

1. **Using `uv`**:

```bash
uv venv .venv --python 3.11
```

2. **Using `virtualenv`**: If you choose to use `virtualenv`, ensure that **Python 3.11** is installed on your machine. You can check if it's installed by running:

```bash
python3.11 --version
```

If Python 3.11 is installed, create the virtual environment with:

```bash
python3.11 -m venv .venv
```

**Note**: If Python 3.11 is not installed on your machine, you will need to install it before proceeding. For macOS, you can install Python 3.11 using `Homebrew`:

```bash
brew install python@3.11
```

### Activate the virtual environment:

Once the virtual environment is created, activate it:

```bash
source .venv/bin/activate
```

### Installing Project Dependencies

Install the project dependencies:

```bash
uv pip install -e '.[dev]'  # Using uv
pip install -e '.[dev]'  # Using vanilla pip
```

If additional packages are missing, try:

```bash
uv pip install -r www/requirements.txt -r www/requirements-dev.txt  # Using uv
```

### Initializing the Test Databases

Initialize the test databases with:

```bash
python -m www.app.db create
```

### Running the FastAPI Application

Serve the FastAPI application in development mode:

```bash
make start
```

## Testing

To run tests, use the following commands:

1. Run autoformatting: `make format`
2. Run static checks: `make static-checks`
3. Run unit tests: `make test`

```bash
make test
```

### Testing Docker Container

To test the Docker container that was pushed to AWS, first authenticate:

```bash
aws ecr get-login-password --region us-east-1 --profile kscale | docker login \
  --username AWS \
  --password-stdin \
  725596835855.dkr.ecr.us-east-1.amazonaws.com  # Our ECR repository
```

Next, pull the latest image:

```bash
docker pull 725596835855.dkr.ecr.us-east-1.amazonaws.com/www:latest
```

Finally, run the image with port 8080 exposed:

```bash
docker run \
  -p 8080:8080 \
  -e ENVIRONMENT='staging' \
  725596835855.dkr.ecr.us-east-1.amazonaws.com/www:latest
```
