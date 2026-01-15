
import requests
import json
import sys

def test_chat():
    url = "http://localhost:8000/api/copilot/chat"
    
    # payload mimicking a user asking about a map with some context
    payload = {
        "messages": [
            {"role": "user", "content": "Which facility is the largest?"}
        ],
        "context": {
            "facilities": [{"name": "Facility A"}, {"name": "Facility B"}],
            "largest_cell": {"name": "Facility A", "area_sq_km": 150.5},
            "selected_facility": None
        }
    }
    
    print(f"Sending request to {url}...")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        print("\nSuccess! Response from AI:")
        print("-" * 50)
        print(data['response'])
        print("-" * 50)
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to backend. Is it running on port 8000?")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        if 'response' in locals():
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
        sys.exit(1)

if __name__ == "__main__":
    test_chat()
