import os

from dotenv import load_dotenv

load_dotenv()


class Secrets:
    INFISICAL_CLIENT_ID = os.environ["INFISICAL_CLIENT_ID"]
    INFISICAL_CLIENT_TOKEN = os.environ["INFISICAL_CLIENT_TOKEN"]
    INFISICAL_PROJECT_ID = "7fb6fa25-4911-4440-88dd-0e4878f3e67d"


class Environment:
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
