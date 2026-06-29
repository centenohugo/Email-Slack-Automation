import os

BUILDING_FILTER = "ZAZ1"
DAYS_THRESHOLD = 21
TEAMS_FILE = os.path.join("sample", "Teams.xlsx")
EMAIL_DOMAIN = "@amazon.es"

# Test mode: all emails go to TEST_EMAIL instead of real recipients
TEST_MODE = True
TEST_EMAIL = "roggen@amazon.es"

DEFAULT_TEMPLATE = "template_table"
SECRET_KEY = "reminder-local-key-2024"
UPLOAD_FOLDER = "uploads"
