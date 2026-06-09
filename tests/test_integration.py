import requests
import random
import time
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
TEST_IMAGE_PATH = os.path.join(REPO_ROOT, "scenesolver-backend", "public", "media", "01bb7218-119b-4394-8d58-663b48527f5a.jpg")
BACKEND_URL = "http://127.0.0.1:5000"

def run_integration_test():
    print("[TEST] Starting E2E Integration Test...")
    
    # Generate unique test user
    rand_id = random.randint(1000, 9999)
    name = f"Test User {rand_id}"
    email = f"testuser{rand_id}@example.com"
    password = "password123"

    # 1. Signup
    signup_url = f"{BACKEND_URL}/api/auth/signup"
    print(f"1. Signing up user: {email}")
    signup_res = requests.post(signup_url, json={"name": name, "email": email, "password": password})
    assert signup_res.status_code == 200, f"Signup failed with status {signup_res.status_code}"
    signup_data = signup_res.json()
    assert signup_data.get("success") is True, f"Signup was not successful: {signup_data}"
    print("SUCCESS: Signup successful.")

    # 2. Login
    login_url = f"{BACKEND_URL}/api/auth/login"
    print("2. Logging in...")
    login_res = requests.post(login_url, json={"email": email, "password": password})
    assert login_res.status_code == 200, f"Login failed with status {login_res.status_code}"
    login_data = login_res.json()
    assert login_data.get("success") is True, f"Login was not successful: {login_data}"
    token = login_data.get("token")
    assert token is not None, "JWT token not found in login response"
    print("SUCCESS: Login successful. JWT token received.")

    # 3. Upload and Analyze Image
    analysis_url = f"{BACKEND_URL}/api/analysis"
    print(f"3. Uploading test image: {TEST_IMAGE_PATH}")
    
    if not os.path.exists(TEST_IMAGE_PATH):
        # Create a dummy image if the file doesn't exist
        print(f"WARNING: Test image {TEST_IMAGE_PATH} not found. Creating a blank image for testing...")
        from PIL import Image
        os.makedirs(os.path.dirname(TEST_IMAGE_PATH), exist_ok=True)
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(TEST_IMAGE_PATH)
        
    headers = {"x-auth-token": token}
    with open(TEST_IMAGE_PATH, 'rb') as f:
        files = {'media': (os.path.basename(TEST_IMAGE_PATH), f, 'image/jpeg')}
        analysis_res = requests.post(analysis_url, headers=headers, files=files)
        
    assert analysis_res.status_code == 201, f"Analysis failed with status {analysis_res.status_code}: {analysis_res.text}"
    analysis_data = analysis_res.json()
    print("SUCCESS: Analysis request completed successfully!")
    print("\n--- AI Results ---")
    print(f"Quick Caption: {analysis_data.get('quickCaption')}")
    print(f"Full Story:    {analysis_data.get('fullStory')}")
    print(f"Scene Keywords:{analysis_data.get('sceneKeywords')}")
    print(f"Found Objects: {analysis_data.get('foundObjects')}")
    print("-------------------\n")

    # 4. Check History Retrieval
    history_url = f"{BACKEND_URL}/api/analysis/history"
    print("4. Fetching user analysis history...")
    history_res = requests.get(history_url, headers=headers)
    assert history_res.status_code == 200, f"Fetching history failed with status {history_res.status_code}"
    history_data = history_res.json()
    assert len(history_data) > 0, "User history is empty, but we just uploaded a file"
    assert history_data[0]["_id"] == analysis_data["_id"], "First entry in history is not the one we just uploaded"
    print("SUCCESS: User history fetched and verified successfully.")
    
    print("\nALL E2E INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_integration_test()
