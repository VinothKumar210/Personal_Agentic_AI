import sys
import os

# Add the parent directory to Python path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import Settings
from app.services.startup_checks import run_startup_checks

def main():
    print("====================================")
    print("Environment Configuration Validation")
    print("====================================")
    
    try:
        # Pydantic Settings will automatically validate
        settings = Settings()
        print("[OK] Environment variables passed Pydantic validation.")
        
        # Run startup checks which verify storage, DB connection, Groq, Chroma
        print("\nRunning startup checks...")
        run_startup_checks()
        print("\n[OK] Startup checks completed.")
    except ValueError as e:
        print("\n[ERROR] Configuration validation failed:")
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print("\n[ERROR] An unexpected error occurred:")
        print(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
