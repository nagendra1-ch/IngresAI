import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.import_data import main as run_import

def main():
    print("Triggering database migration and normalized data import...")
    run_import()
    print("Database normalization completed successfully.")

if __name__ == "__main__":
    main()
