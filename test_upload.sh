#!/bin/bash
# Upload
TIMESTAMP=$(date +%s)
NONCE="upload$(date +%s%N)"

echo "Uploading..."
curl -X POST http://localhost:8000/api/v1/upload/music/ \
  -H "Authorization: DID-Signature did:example:locke:fakesig:${TIMESTAMP}:${NONCE}" \
  -F "file=@test.txt"

echo -e "\nWaiting 5 seconds for processing..."
sleep 5

# Download
TIMESTAMP=$(date +%s)
NONCE="download$(date +%s%N)"

# Get the last uploaded object ID (assuming ID 1 for first upload, we might need a dynamic way if it's already uploaded)
# Let's list objects to find the ID
echo "Listing objects..."
curl -s -X GET "http://localhost:8000/api/v1/objects/?page=1&page_size=1" \
  -H "Authorization: DID-Signature did:example:locke:fakesig:${TIMESTAMP}:${NONCE}" > objects.json

OBJ_ID=$(grep -o '"id": [0-9]*' objects.json | head -1 | cut -d' ' -f2)

if [ -z "$OBJ_ID" ]; then
    echo "Could not find object ID"
    exit 1
fi

echo "Downloading object $OBJ_ID..."
curl -X GET "http://localhost:8000/api/v1/download/${OBJ_ID}/" \
  -H "Authorization: DID-Signature did:example:locke:fakesig:${TIMESTAMP}:${NONCE}" \
  -o downloaded_test.txt

echo -e "\nDownloaded content:"
cat downloaded_test.txt
