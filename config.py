import os
from dotenv import load_dotenv

load_dotenv()

BUILDING_FILTER = "ZAZ1"
DAYS_THRESHOLD = 21
TEAMS_FILE = os.path.join("sample", "Teams.xlsx")
EMAIL_DOMAIN = "@amazon.es"

SECRET_KEY = os.environ["SECRET_KEY"]
TEST_EMAIL = os.environ["TEST_EMAIL"]

DEFAULT_TEMPLATE = "template_table"
UPLOAD_FOLDER = "uploads"
EMAIL_SEND_DELAY = 1.5
