#!/bin/bash

# Usage: ./load_test.sh [request_type] [total_requests] [duration_secs]
# request_type: one | two | both
# total_requests: Number of requests to send
# duration_secs: Duration to spread requests over

# Check for GNU parallel
if ! command -v parallel &> /dev/null; then
  echo "GNU parallel is required. Install it with: sudo apt install parallel"
  exit 1
fi

# Validate input
if [ $# -ne 3 ]; then
  echo "Usage: $0 [one|two|both] [total_requests] [duration_secs]"
  exit 1
fi

REQ_TYPE="$1"
TOTAL_REQUESTS="$2"
DURATION="$3"
DELAY=$(awk "BEGIN {print $DURATION / $TOTAL_REQUESTS}")

URL="http://localhost:8000/"

BODY_ONE='{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{
        "kind": "text",
        "text": "one"
      }],
      "message_id": "msg-one",
      "kind": "message"
    }
  },
  "id": "req-one"
}'

BODY_TWO='{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{
        "kind": "text",
        "text": "two"
      }],
      "message_id": "msg-one",
      "kind": "message"
    }
  },
  "id": "req-one"
}'

send_request() {
  local TYPE=$1
  local BODY=""
  if [ "$TYPE" == "one" ]; then
    BODY="$BODY_ONE"
  elif [ "$TYPE" == "two" ]; then
    BODY="$BODY_TWO"
  else
    echo "Unknown request type: $TYPE"
    return 1
  fi

  curl -s -X POST "$URL" \
    -H "Content-Type: application/json" \
    -d "$BODY" > /dev/null
}

export -f send_request
export URL BODY_ONE BODY_TWO

# Generate request plan
generate_requests() {
  for ((i=1; i<=TOTAL_REQUESTS; i++)); do
    case "$REQ_TYPE" in
      one) echo "send_request one" ;;
      two) echo "send_request two" ;;
      both)
        if (( RANDOM % 2 )); then
          echo "send_request one"
        else
          echo "send_request two"
        fi
        ;;
      *)
        echo "Invalid request type: $REQ_TYPE"
        exit 1
        ;;
    esac
    sleep "$DELAY"
  done
}

# Run requests with parallel
generate_requests | parallel -j 50 --line-buffer
