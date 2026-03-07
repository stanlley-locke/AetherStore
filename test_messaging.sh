CONV_ID="83d0671b-ac46-444c-abe3-27b4e4aa9bed"
ALICE="DID-Signature did:example:alice:fakesig:$(date +%s):nonce$(date +%s%N)"
BOB_AUTH="DID-Signature did:example:bob:fakesig:$(date +%s):nonce$(date +%s%N)"

# Send a message
curl -s -X POST "http://localhost:8000/api/v1/messaging/conversations/${CONV_ID}/send/" \
  -H "Authorization: ${ALICE}" \
  -H "Content-Type: application/json" \
  -d '{"body": "Hello Bob! This is Alice from AetherStore Messaging.", "type": "text"}'
