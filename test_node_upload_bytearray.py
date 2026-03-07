import httpx
import os

def test_upload_bytearray():
    data = bytearray(os.urandom(51 * 1024))
    url = "http://localhost:8009/shard/19ba101143f3d42466c90556cadb2ce51e47a72ba2d6fe434d27d81376341e1f/0/2"
    
    with httpx.Client() as client:
        try:
            response = client.put(url, content=data)
            print(f"Status: {response.status_code}")
            print(f"Content: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_upload_bytearray()
