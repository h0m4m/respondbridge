# MongoDB Schema Documentation

Complete schema documentation for the Respond.io Webhook Bridge MongoDB collections.

---

## Collections Overview

- **conversations**: Stores conversation metadata and aggregate information
- **messages**: Stores individual messages with full details

When `TEST_MODE=true`, data is saved to `test_conversations` and `test_messages` instead.

---

## Messages Collection

Stores individual messages from both incoming and outgoing traffic.

### Schema Structure

```javascript
{
  // Primary identifier
  "_id": "1763654646000000",                    // String: messageId from respond.io

  // Core message fields
  "chat_id": "+971566644755",                   // String: Phone number or contact_id
  "ts": ISODate("2025-11-20T17:04:06.000Z"),   // Date: Message timestamp
  "sender": "+971566644755",                    // String: Sender identifier (phone/email/source)
  "type": "attachment",                         // String: Message type
  "message_type": "incoming",                   // String: "incoming" or "outgoing"

  // Sender information object
  "sender_info": {
    // For incoming messages:
    "phone": "+971566644755",                   // String: Sender phone
    "contact_id": 337133261,                    // Number: Contact ID
    "name": "Humam Mourad"                      // String: Full name

    // For outgoing messages (user):
    "id": 876197,                               // Number: User ID
    "email": "rawan.alasali@fastercars.ae",    // String: User email
    "firstName": "Rawan",                       // String: First name
    "lastName": "Alasali",                      // String: Last name
    "role": "user"                              // String: User role

    // For outgoing messages (system/echo):
    "source": "Echo Message"                    // String: Source identifier
  },

  // Respond.io metadata
  "channel_message_id": "wamid.HBgM...",        // String: WhatsApp/channel message ID
  "contact_id": 337133261,                      // Number: Contact ID
  "channel_id": 438771,                         // Number: Channel ID
  "channel_name": "Faster AE",                  // String: Channel name
  "channel_source": "whatsapp_business",        // String: Channel source type
  "event_type": "message.received",             // String: Event type
  "event_id": "d8481901-ec53-4b25-bc52-d96f483805a3", // String: Unique event ID
  "source": "User",                             // String: Message source (User/Echo Message/etc)

  // Message status tracking
  "status": [
    {
      "value": "sent",                          // String: Status value
      "timestamp": 1763652789000,               // Number: Unix timestamp (ms)
      "message": "Optional failure reason"      // String: Only for failed status
    }
  ],

  // Timestamps
  "created_at": ISODate("2025-11-20T17:04:06.000Z"), // Date: Record creation time

  // Complete message content (preserves all original data)
  "raw_message": {
    "type": "attachment",                       // String: Message type
    "text": "Message text",                     // String: For text messages
    "messageTag": "ACCOUNT_UPDATE",             // String: Optional message tag
    "attachment": { /* ... */ }                 // Object: For attachment messages
  },

  // Optional: Message tag (duplicated for easy querying)
  "message_tag": "ACCOUNT_UPDATE",              // String: Message tag if present

  // Type-specific fields (extracted for convenience)

  // For attachment type messages:
  "attachment": {
    "type": "image",                            // String: image/video/document/file/audio
    "url": "https://...",                       // String: File URL
    "fileName": "File.jpg",                     // String: Original filename
    "mimeType": "image/jpeg",                   // String: MIME type
    "size": "14324",                            // String: File size in bytes
    "ext": "jpg",                               // String: File extension
    "description": "Another image"              // String: Caption/description
  },

  // For image type messages (legacy):
  "image_url": "https://...",                   // String: Image URL

  // For video type messages (legacy):
  "video_url": "https://...",                   // String: Video URL

  // For document type messages (legacy):
  "document_url": "https://...",                // String: Document URL
  "filename": "document.pdf",                   // String: Document filename

  // For audio type messages (legacy):
  "audio_url": "https://...",                   // String: Audio URL

  // For location type messages:
  "location": {
    "latitude": 25.2048,                        // Number: Latitude
    "longitude": 55.2708,                       // Number: Longitude
    "address": "Dubai, UAE"                     // String: Address text
  }
}
```

### Message Types

| Type | Description | Additional Fields |
|------|-------------|-------------------|
| `text` | Plain text messages | `raw_message.text` |
| `attachment` | Attachments with nested details | `attachment` object |
| `image` | Image messages (legacy) | `image_url` |
| `video` | Video messages (legacy) | `video_url` |
| `document` | Document messages (legacy) | `document_url`, `filename` |
| `audio` | Audio messages (legacy) | `audio_url` |
| `location` | Location sharing | `location` object |

### Indexes (Recommended)

```javascript
db.messages.createIndex({ "chat_id": 1, "ts": -1 })
db.messages.createIndex({ "contact_id": 1 })
db.messages.createIndex({ "channel_id": 1 })
db.messages.createIndex({ "message_type": 1 })
db.messages.createIndex({ "type": 1 })
db.messages.createIndex({ "event_id": 1 }, { unique: true })
```

---

## Conversations Collection

Stores conversation-level metadata and aggregate statistics.

### Schema Structure

```javascript
{
  // Primary identifier
  "_id": "+971566644755",                       // String: Phone number or contact_id

  // Timestamps
  "created_at": ISODate("2025-01-08T10:30:29.843Z"),      // Date: Conversation creation
  "updated_at": ISODate("2025-12-30T08:07:02.000Z"),      // Date: Last update
  "first_message_ts": ISODate("2023-10-01T12:15:00.000Z"), // Date: First message
  "last_message_ts": ISODate("2024-12-30T08:07:02.000Z"),  // Date: Most recent message

  // Aggregate statistics
  "message_count": 24,                          // Number: Total message count

  // Media counts by type
  "media_counts": {
    "image": 3,                                 // Number: Image count
    "video": 1,                                 // Number: Video count
    "document": 2,                              // Number: Document count
    "audio": 0,                                 // Number: Audio count
    "file": 0                                   // Number: Generic file count
  },

  // Channel information
  "channel": ["WhatsApp", "Telegram"],          // Array[String]: List of channels used

  "channel_info": {
    "id": 438771,                               // Number: Primary channel ID
    "name": "Faster AE",                        // String: Channel name
    "source": "whatsapp_business",              // String: Channel source
    "lastMessageTime": 1763652213,              // Number: Unix timestamp (seconds)
    "lastIncomingMessageTime": 1763738601       // Number: Unix timestamp (seconds)
  },

  // Contact information
  "contact": {
    "id": 337133261,                            // Number: Contact ID
    "firstName": "Humam",                       // String: First name
    "lastName": "Mourad",                       // String: Last name
    "phone": "+971566644755",                   // String: Phone number
    "email": "john@example.com",                // String: Email (nullable)
    "language": "en",                           // String: Language code (nullable)
    "profilePic": "https://...",                // String: Profile picture URL (nullable)
    "countryCode": "AE",                        // String: Country code
    "status": "open"                            // String: Conversation status
  },

  // Assignee information (optional)
  "assignee": {
    "id": 876197,                               // Number: Assignee user ID
    "email": "rawan.alasali@fastercars.ae",    // String: Assignee email
    "firstName": "Rawan",                       // String: First name
    "lastName": "Alasali",                      // String: Last name
    "role": "user"                              // String: User role
  },

  // Enrichment metadata (optional, from legacy data)
  "enriched_at": ISODate("2025-03-15T10:30:00.000Z") // Date: When enrichment occurred
}
```

### Conversation Status Values

| Status | Description |
|--------|-------------|
| `open` | Active conversation |
| `closed` | Closed conversation |
| `pending` | Awaiting response |
| `resolved` | Issue resolved |

### Indexes (Recommended)

```javascript
db.conversations.createIndex({ "updated_at": -1 })
db.conversations.createIndex({ "last_message_ts": -1 })
db.conversations.createIndex({ "contact.id": 1 })
db.conversations.createIndex({ "contact.status": 1 })
db.conversations.createIndex({ "assignee.id": 1 })
db.conversations.createIndex({ "channel": 1 })
```

---

## Common Query Patterns

### Get all messages for a conversation

```javascript
db.messages.find({
  "chat_id": "+971566644755"
}).sort({ "ts": 1 })
```

### Get conversation with latest messages

```javascript
// Get conversation
const conv = db.conversations.findOne({ "_id": "+971566644755" })

// Get recent messages
const messages = db.messages.find({
  "chat_id": "+971566644755"
}).sort({ "ts": -1 }).limit(50)
```

### Find conversations by assignee

```javascript
db.conversations.find({
  "assignee.email": "rawan.alasali@fastercars.ae"
}).sort({ "last_message_ts": -1 })
```

### Get all image attachments for a conversation

```javascript
db.messages.find({
  "chat_id": "+971566644755",
  "type": "attachment",
  "attachment.type": "image"
}).sort({ "ts": -1 })
```

### Find conversations with media

```javascript
db.conversations.find({
  "media_counts": { $exists: true, $ne: {} }
})
```

### Get unassigned open conversations

```javascript
db.conversations.find({
  "contact.status": "open",
  $or: [
    { "assignee": { $exists: false } },
    { "assignee.id": null }
  ]
}).sort({ "last_message_ts": -1 })
```

### Search messages by text content

```javascript
db.messages.find({
  "raw_message.text": { $regex: "keyword", $options: "i" }
}).sort({ "ts": -1 })
```

### Get message counts by channel

```javascript
db.messages.aggregate([
  {
    $group: {
      _id: "$channel_name",
      count: { $sum: 1 }
    }
  },
  { $sort: { count: -1 } }
])
```

### Get active conversations (messages in last 24 hours)

```javascript
const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000)

db.conversations.find({
  "last_message_ts": { $gte: yesterday }
}).sort({ "last_message_ts": -1 })
```

---

## Data Migration Notes

### From Old Schema to New Schema

The webhook bridge maintains backward compatibility with the old schema:

**Old conversations schema:**
```javascript
{
  "_id": "+971585521050",
  "created_at": Date,
  "first_message_ts": Date,
  "last_message_ts": Date,
  "media_counts": { /* ... */ },
  "message_count": Number,
  "updated_at": Date,
  "channel": ["Yazan"],
  "enriched_at": Date
}
```

**Old messages schema:**
```javascript
{
  "_id": ObjectId,
  "chat_id": "+971569877058",
  "ts": Date,
  "sender": "+971588855332",
  "type": "text",
  "text": "Message text",
  "message_type": "outgoing"
}
```

### Key Differences

1. **Messages now use respond.io messageId as _id** (String instead of ObjectId)
2. **Added sender_info object** with complete sender details
3. **Added raw_message field** preserving all original webhook data
4. **Added contact and channel_info objects** to conversations
5. **Timestamps in milliseconds** converted to proper Date objects
6. **Attachment handling** with structured attachment object

---

## Test Mode Collections

When `TEST_MODE=true` in `.env`:

- Data saves to `test_conversations` and `test_messages`
- Schema is identical to production collections
- Allows safe testing without affecting production data
- Console logging shows full webhook JSON and database operations

To switch to production:
```env
TEST_MODE=false
```

Then restart the Flask application.
