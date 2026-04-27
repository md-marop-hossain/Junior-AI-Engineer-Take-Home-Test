# StayEase Chat API

Two endpoints power the guest-facing chat. Both accept and return JSON and live
under `/api/chat/{conversation_id}`.

| Convention | Value |
| ---------- | ----- |
| Local URL  | `http://127.0.0.1:8000` |
| Encoding   | `application/json; charset=utf-8` |
| Dates      | ISO-8601 — `YYYY-MM-DD` for dates, `YYYY-MM-DDTHH:MM:SSZ` for timestamps |
| Currency   | All prices are integer **BDT** (no decimal places) |

`conversation_id` is a client-generated UUID. The client picks any UUID it
likes on the first turn; the server creates the conversation row automatically.

---

## 1. `POST /api/chat/{conversation_id}/message`

Append a guest turn, run the LangGraph agent, persist the assistant reply, and
return it.

### Request

**Path parameter**

| Name              | Type   | Required | Description                         |
| ----------------- | ------ | -------- | ----------------------------------- |
| `conversation_id` | `uuid` | yes      | Identifies the conversation thread. |

**Body**

```json
{
  "message": "string",
  "guest_phone": "string | null"
}
```

| Field         | Type     | Required | Notes                                                      |
| ------------- | -------- | -------- | ---------------------------------------------------------- |
| `message`     | `string` | yes      | Guest's message. 1–2 000 characters.                       |
| `guest_phone` | `string` | no       | E.164 phone number — saved once and reused for bookings.   |

### Response — `200 OK`

```json
{
  "conversation_id": "uuid",
  "response": "string",
  "intent": "search | details | book | escalate | unknown",
  "escalated": false,
  "tool_result": { } ,
  "created_at": "2026-04-27T10:14:32Z"
}
```

| Field         | Type      | Notes                                                             |
| ------------- | --------- | ----------------------------------------------------------------- |
| `response`    | `string`  | Assistant's reply — ready to display to the guest.               |
| `intent`      | `string`  | Classified intent for this turn; useful for client-side analytics. |
| `escalated`   | `boolean` | `true` when a human teammate has been notified.                   |
| `tool_result` | `object`  | Structured payload from the tool that ran. `null` if no tool ran. |
| `created_at`  | `string`  | UTC timestamp of the assistant turn.                              |

### Example — Search in Cox's Bazar

**Request**

```http
POST /api/chat/3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e/message
Content-Type: application/json

{
  "message": "I need a room in Cox's Bazar for 2 nights for 2 guests",
  "guest_phone": "+8801711000111"
}
```

**Response**

```json
{
  "conversation_id": "3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e",
  "response": "I found 5 places in Cox's Bazar for 28–30 Apr — Sea Pearl Beach Suite at ৳6,500/night, Mermaid Eco Resort Cottage at ৳5,500/night, Sayeman Heritage Studio at ৳4,200/night, Long Beach Apartment at ৳3,800/night, and Laboni Beach Guest House at ৳2,800/night. Want details on any of them?",
  "intent": "search",
  "escalated": false,
  "tool_result": {
    "count": 5,
    "results": [
      { "listing_id": "25e3d0e4-cdd9-41a9-a2a6-9d74f0e77076", "title": "Sea Pearl Beach Suite",      "price_per_night_bdt": 6500, "max_guests": 2, "rating": 4.8 },
      { "listing_id": "7b931f79-82ed-4ff2-9a39-54cf6ffa828d", "title": "Mermaid Eco Resort Cottage",  "price_per_night_bdt": 5500, "max_guests": 3, "rating": 4.6 },
      { "listing_id": "1bdc47fd-2b3e-4cb7-b5e7-0074269191a6", "title": "Sayeman Heritage Studio",     "price_per_night_bdt": 4200, "max_guests": 2, "rating": 4.3 },
      { "listing_id": "6b7bfc95-f507-4300-89d4-373d12f6d613", "title": "Long Beach Apartment",        "price_per_night_bdt": 3800, "max_guests": 4, "rating": 4.1 },
      { "listing_id": "b35879c8-4e0d-4aba-b81a-99a906535261", "title": "Laboni Beach Guest House",    "price_per_night_bdt": 2800, "max_guests": 2, "rating": 3.9 }
    ]
  },
  "created_at": "2026-04-27T06:12:27Z"
}
```

### Error Responses

| Status | When                                                                    |
| ------ | ----------------------------------------------------------------------- |
| `422`  | Request body fails validation (missing `message`, value out of range).  |
| `500`  | Unhandled server error (LLM call failed, DB unreachable, etc.).         |

---

## 2. `GET /api/chat/{conversation_id}/history`

Return the full transcript for a conversation, oldest turn first. Used by the
chat UI to rehydrate the thread when the guest reopens the app.

### Request

**Path parameter**

| Name              | Type   | Required |
| ----------------- | ------ | -------- |
| `conversation_id` | `uuid` | yes      |

**Query parameters**

| Name     | Type        | Default | Notes                                                          |
| -------- | ----------- | ------- | -------------------------------------------------------------- |
| `limit`  | `integer`   | `50`    | Maximum turns to return (1–200).                               |
| `before` | `timestamp` | —       | ISO-8601 UTC. Return only turns with `created_at < before`. Pagination cursor. |

### Response — `200 OK`

```json
{
  "conversation_id": "uuid",
  "escalated": false,
  "messages": [
    {
      "role": "user | assistant",
      "content": "string",
      "created_at": "2026-04-27T10:14:30Z"
    }
  ],
  "next_before": "2026-04-27T10:14:30Z | null"
}
```

`next_before` is `null` when there are no older turns (i.e. the full history
fits in one page).

### Example — Full booking thread

**Request**

```http
GET /api/chat/3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e/history?limit=50
```

**Response**

```json
{
  "conversation_id": "3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e",
  "escalated": false,
  "messages": [
    {
      "role": "user",
      "content": "I need a room in Cox's Bazar for 2 nights for 2 guests",
      "created_at": "2026-04-27T06:12:25Z"
    },
    {
      "role": "assistant",
      "content": "I found 5 places in Cox's Bazar for 28–30 Apr — Sea Pearl Beach Suite at ৳6,500/night, Mermaid Eco Resort Cottage at ৳5,500/night… Want details on any of them?",
      "created_at": "2026-04-27T06:12:27Z"
    },
    {
      "role": "user",
      "content": "Tell me more about the Sea Pearl Beach Suite",
      "created_at": "2026-04-27T06:14:38Z"
    },
    {
      "role": "assistant",
      "content": "The Sea Pearl Beach Suite is a beachfront suite with panoramic Bay of Bengal views, a king bed, and a private balcony — ৳6,500/night, max 2 guests. Amenities include WiFi, AC, breakfast, pool, and direct beach access. Would you like to book it?",
      "created_at": "2026-04-27T06:14:40Z"
    },
    {
      "role": "user",
      "content": "Book it for Rahim Ahmed, phone +8801711000111, check in 2026-04-28, check out 2026-04-30, 2 guests",
      "created_at": "2026-04-27T06:16:18Z"
    },
    {
      "role": "assistant",
      "content": "All done, Rahim! Your booking is confirmed — Sea Pearl Beach Suite, 28–30 Apr, 2 guests. Total ৳13,000. Booking ID: e7f2a1b3-9c4d-4e8f-a2b1-3c4d5e6f7a8b.",
      "created_at": "2026-04-27T06:16:21Z"
    }
  ],
  "next_before": null
}
```

### Error Responses

| Status | When                                                             |
| ------ | ---------------------------------------------------------------- |
| `404`  | `conversation_id` does not exist — `{"detail": "conversation_not_found"}`. |
| `422`  | `limit` out of range or `before` is not a parseable timestamp.  |
| `500`  | Unhandled server error.                                          |

---

## 3. Local Test Cases

All commands target `http://127.0.0.1:8000`. Run them in order — Tests 1 → 2
→ 3 → 4 form a complete search → details → book → history flow.

---

### Test 1 — Search (Cox's Bazar, 2 nights, 2 guests)

```bash
curl -X POST http://127.0.0.1:8000/api/chat/3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e/message \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"I need a room in Cox's Bazar for 2 nights for 2 guests\", \"guest_phone\": \"+8801711000111\"}"
```

**Expected:** `intent: "search"`, `tool_result.count >= 1`, response lists properties with ৳ prices.

---

### Test 2 — Listing details

Ask about the Sea Pearl Beach Suite by name (the agent remembers the UUID from
the previous turn via `agent_state`):

```bash
curl -X POST http://127.0.0.1:8000/api/chat/3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e/message \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Tell me more about the Sea Pearl Beach Suite\"}"
```

**Expected:** `intent: "details"`, response includes description, amenities, and address.

---

### Test 3 — Book

The agent already knows the listing UUID and search dates from prior turns:

```bash
curl -X POST http://127.0.0.1:8000/api/chat/3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e/message \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Book it for Rahim Ahmed, phone +8801711000111, check in 2026-04-28, check out 2026-04-30, 2 guests\"}"
```

**Expected:** `intent: "book"`, `tool_result.status: "confirmed"`, response shows `booking_id` and total ৳13,000.

---

### Test 4 — Conversation history

```bash
curl "http://127.0.0.1:8000/api/chat/3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e/history?limit=50"
```

**Expected:** `200 OK`, `messages` contains all 6 turns in order, `next_before: null`.

---

### Test 5 — Escalation (off-topic question)

```bash
curl -X POST http://127.0.0.1:8000/api/chat/aaaaaaaa-0000-0000-0000-000000000001/message \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Can you recommend a good restaurant near Laboni Beach?\"}"
```

**Expected:** `escalated: true`, response says a human teammate will reply.

---

### Test 6 — Search in Dhaka

```bash
curl -X POST http://127.0.0.1:8000/api/chat/bbbbbbbb-0000-0000-0000-000000000002/message \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Find me a hotel in Dhaka for 1 night, 1 guest, checking in 2026-05-01\"}"
```

**Expected:** `intent: "search"`, results include The Westin Dhaka Deluxe Room at ৳8,500/night.

---

### Test 7 — 404 for unknown conversation

```bash
curl "http://127.0.0.1:8000/api/chat/00000000-0000-0000-0000-000000000000/history"
```

**Expected:** `404`, body `{"detail": "conversation_not_found"}`.

---

### Test 8 — Health check

```bash
curl http://127.0.0.1:8000/health
```

**Expected:** `{"status": "ok"}`.

---

### Test 9 — Pagination cursor

First run Test 4 to get timestamps, then page backwards:

```bash
curl "http://127.0.0.1:8000/api/chat/3f8a2c6e-9b1d-4a7f-8c2e-5d6b9f1a2c3e/history?limit=2&before=2026-04-27T06:16:00Z"
```

**Expected:** Returns at most 2 messages before the given timestamp; `next_before` is set if there are older turns.
