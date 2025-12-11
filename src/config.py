#we use dynamic paths. This file calculates where your data folder is, no matter where you put the project.

import os
from dotenv import load_dotenv

# 1. Load environment variables from .env
load_dotenv()

# 2. Fetch API Keys (Safety Check)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

if not GEMINI_API_KEY:
    print("⚠️ WARNING: Add gemini api key")

# 3. Dynamic Path Calculation
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)

# 4. Define Critical Data Paths
DATA_DIR = os.path.join(ROOT_DIR, "data")
RESUMES_DIR = os.path.join(DATA_DIR, "resumes")
CHROME_USER_DATA = os.path.join(DATA_DIR, "chrome_profile")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

# 5. Auto-Create Folders
os.makedirs(RESUMES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

print(f"✅ Config loaded. Root path: {ROOT_DIR}")