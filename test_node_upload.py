import httpx
import os

def test_upload_51kb():
    # Make a 51KB random string
    data = os.urandom(51 * 1024)
    # Target URL
    url = "http://localhost:8001/shard/19ba101143f3d42466c90556cadb2ce51e47a72ba2d6fe434d27d81376341e1f/0/1"
    
    with httpx.Client() as client:
        response = client.put(url, content=data)
        print(f"Status: {response.status_code}")
        print(f"Content: {response.text}")

if __name__ == "__main__":
    test_upload_51kb()
