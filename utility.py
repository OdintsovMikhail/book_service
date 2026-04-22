import pyodbc
from dotenv import load_dotenv
import os

load_dotenv()
 
def get_connection() -> pyodbc.Connection:
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_DATABASE')};"
        f"UID={os.getenv('DB_USERNAME')};"
        f"PWD={os.getenv('DB_PASSWORD')};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def get_api_urls() -> dict:
    services = {
        "user": os.getenv('USER_SERVICE'),
        "meeting": os.getenv('MEETING_SERVICE'),
        "book": os.getenv('BOOK_SERVICE')
    }

    return services