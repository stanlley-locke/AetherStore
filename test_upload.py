import subprocess
import time

def run(cmd):
    return subprocess.check_output(cmd, shell=True).decode()

# Upload
print("Uploading...")
res = run("get_auth() { echo \"DID-Signature did:example:test_user:fakesig:$(date +%s):test$(date +%s%N)\"; }; curl -s -X POST http://localhost:8000/api/v1/upload/mybucket/ -H \"Authorization: $(get_auth)\" -F \"file=@test.txt\"")
print(res)

print("Waiting for celery...")
time.sleep(15)

# List
print("Listing...")
res = run("get_auth() { echo \"DID-Signature did:example:test_user:fakesig:$(date +%s):test$(date +%s%N)\"; }; curl -s -X GET \"http://localhost:8000/api/v1/objects/?page=1&page_size=1&sort=-created_at\" -H \"Authorization: $(get_auth)\"")
print(res)
