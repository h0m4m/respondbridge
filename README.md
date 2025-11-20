# Respond.io Webhook Bridge

Flask application that receives webhooks from respond.io platform and stores conversation data in MongoDB.

## Features

- **4 Webhook Endpoints**: Separate endpoints for Faster AI and VIP databases (incoming/outgoing)
- **Test Mode**: Feature flag to log webhooks to test collections for debugging
- **Rich Data Mapping**: Comprehensive mapping from respond.io webhooks to MongoDB schema
- **Multiple Message Types**: Supports text, image, video, document, audio, location, and more
- **Conversation Tracking**: Automatic conversation updates with message counts and metadata

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

The `.env` file is already configured with your MongoDB credentials. To enable test mode, update:

```env
TEST_MODE=true
```

### 3. Run the Application

```bash
python app.py
```

The server will start on port 8000 by default.

## Endpoints

### Webhook Endpoints

- `POST /webhook/faster/incoming` - Faster AI incoming messages
- `POST /webhook/faster/outgoing` - Faster AI outgoing messages
- `POST /webhook/vip/incoming` - VIP incoming messages
- `POST /webhook/vip/outgoing` - VIP outgoing messages

### Utility Endpoints

- `GET /` - API information
- `GET /health` - Health check

## Test Mode

When `TEST_MODE=true` in `.env`:

- Webhooks are logged to console with full JSON data
- Data is saved to `test_conversations` and `test_messages` collections
- Useful for debugging new message types and webhook formats

Example log output in test mode:

```
================================================================================
TEST MODE - INCOMING WEBHOOK RECEIVED
================================================================================
{
  "contact": {...},
  "message": {...},
  ...
}
================================================================================
```

## MongoDB Collections

### Conversations Collection

Stores conversation metadata:

```json
{
  "_id": "+971585521050",
  "created_at": "2024-01-08T10:30:29.843Z",
  "first_message_ts": "2023-10-01T12:15:00.000Z",
  "last_message_ts": "2024-12-30T08:07:02.000Z",
  "message_count": 24,
  "media_counts": {
    "image": 3,
    "video": 1,
    "document": 2
  },
  "channel": ["WhatsApp", "Telegram"],
  "contact": {
    "id": 1,
    "firstName": "John",
    "lastName": "Doe",
    "phone": "+971585521050",
    "email": "john@example.com"
  },
  "updated_at": "2024-12-30T08:07:02.000Z"
}
```

### Messages Collection

Stores individual messages:

```json
{
  "_id": "1262965213",
  "chat_id": "+971585521050",
  "ts": "2024-12-30T08:07:02.000Z",
  "sender": "+971585521050",
  "type": "text",
  "text": "Hello world",
  "message_type": "incoming",
  "channel_id": 123,
  "channel_name": "WhatsApp",
  "channel_source": "whatsapp",
  "status": [
    {"value": "sent", "timestamp": 1662965213},
    {"value": "delivered", "timestamp": 1662965214}
  ],
  "event_type": "message.received",
  "created_at": "2024-12-30T08:07:02.000Z"
}
```

## Supported Message Types

- **text** - Plain text messages
- **image** - Images with URL
- **video** - Videos with URL
- **document** - Documents/files with URL and filename
- **audio** - Audio files with URL
- **location** - Geographic locations with coordinates

## Testing Webhooks

Use curl or Postman to test webhooks:

```bash
curl -X POST http://localhost:8000/webhook/faster/incoming \
  -H "Content-Type: application/json" \
  -d '{
    "contact": {
      "id": 1,
      "firstName": "John",
      "lastName": "Doe",
      "phone": "+60123456789"
    },
    "message": {
      "messageId": 123,
      "timestamp": 1662965213,
      "message": {
        "type": "text",
        "text": "Hello"
      }
    },
    "channel": {
      "id": 1,
      "name": "WhatsApp",
      "source": "whatsapp"
    },
    "event_type": "message.received"
  }'
```

## Production Deployment

For production, use gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Environment Variables

- `MONGO_URI` - Faster AI MongoDB connection string
- `DB_NAME` - Faster AI database name
- `VIP_MONGO_URI` - VIP MongoDB connection string
- `VIP_DB_NAME` - VIP database name
- `PORT` - Server port (default: 8000)
- `FLASK_ENV` - Flask environment (development/production)
- `TEST_MODE` - Enable test mode (true/false)

## Adding Support for New Message Types

1. Set `TEST_MODE=true` in `.env`
2. Send webhook to appropriate endpoint
3. Check console logs for full webhook structure
4. Update `process_webhook()` method in `app.py` to handle new fields
5. Test again to verify data is saved correctly
6. Set `TEST_MODE=false` when ready for production
