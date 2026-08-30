import requests
import csv
import io
import sys

BASE_URL = "http://localhost:8000"

def run_tests():
    try:
        print("1. Testing Health Endpoint...")
        res = requests.get(f"{BASE_URL}/api/health")
        if res.status_code != 200:
            print(f"FAILED: Health check returned {res.status_code}")
            sys.exit(1)
        print(" -> Health OK.")

        print("\n2. Testing Dashboard & Seed Data...")
        res = requests.get(f"{BASE_URL}/api/dashboard")
        data = res.json()
        if data.get("runs", 0) == 0:
            print("FAILED: Database is empty. Seed data failed to generate.")
            sys.exit(1)
        print(f" -> Dashboard OK. Found {data['runs']} reconciliation runs.")

        print("\n3. Testing Exceptions DTO for RCA and Compliance fields...")
        res = requests.get(f"{BASE_URL}/api/exceptions")
        exceptions = res.json()
        if len(exceptions) == 0:
            print("FAILED: No exceptions found to test.")
            sys.exit(1)
            
        sample = exceptions[0]
        if "rcaCategory" not in sample or "complianceStatus" not in sample:
            print(f"FAILED: Missing new fields in DTO. Received keys: {list(sample.keys())}")
            sys.exit(1)
        print(f" -> DTO OK. Verified RCA: '{sample['rcaCategory']}', Compliance: '{sample['complianceStatus']}'.")

        print("\n4. Testing CSV Export Structure...")
        res = requests.get(f"{BASE_URL}/api/export/exceptions.csv")
        reader = csv.reader(io.StringIO(res.text))
        headers = next(reader)
        if "rca_category" not in headers or "compliance_status" not in headers:
            print(f"FAILED: CSV headers missing new fields. Found: {headers}")
            sys.exit(1)
        print(" -> CSV Export OK. Headers successfully mapped.")

        print("\nSUCCESS: All backend checks passed. The API is ready.")

    except requests.exceptions.ConnectionError:
        print("\nFAILED: Could not connect to the server. Is FastAPI running on port 8000?")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()