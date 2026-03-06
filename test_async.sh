#!/bin/bash
# test_async.sh

get_auth() {
  echo "DID-Signature did:example:test_user:fakesig:$(date +%s):test$(date +%s%N)"
}

OBJ_ID="1dd68fa1-346b-42df-a796-6d6b4a5b1e33"
echo "Initiating download for $OBJ_ID"

RESPONSE=$(curl -s -X GET "http://localhost:8000/api/v1/download/${OBJ_ID}/" -H "Authorization: $(get_auth)")
echo "Response: $RESPONSE"

# Extract task_id using grep and sed or node (since we have standard bash, lets just parse json crudely)
TASK_ID=$(echo $RESPONSE | grep -o '"task_id":"[^"]*' | grep -o '[^"]*$')

if [ -z "$TASK_ID" ]; then
    echo "Failed to get task ID"
    exit 1
fi

echo "Task ID: $TASK_ID"

# Poll status
for i in {1..15}; do
    echo "Polling status... attempt $i"
    STATUS_RESP=$(curl -s -X GET "http://localhost:8000/api/v1/download/status/${TASK_ID}/" -H "Authorization: $(get_auth)")
    echo "Status: $STATUS_RESP"
    
    if echo "$STATUS_RESP" | grep -q '"status":"success"'; then
        echo "Download task succeeded!"
        break
    elif echo "$STATUS_RESP" | grep -q '"status":"failed"'; then
        echo "Download task failed!"
        exit 1
    fi
    sleep 2
done

echo "Attempting to retrieve file..."
curl -v -X GET "http://localhost:8000/api/v1/download/file/${TASK_ID}/" -H "Authorization: $(get_auth)" -o local_test.txt

echo "Head of downloaded file:"
head -n 5 local_test.txt
