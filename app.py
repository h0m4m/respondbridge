import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configuration
PORT = int(os.getenv('PORT', 8000))
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

# MongoDB connections
FASTER_CLIENT = MongoClient(os.getenv('MONGO_URI'))
FASTER_DB = FASTER_CLIENT[os.getenv('DB_NAME')]

VIP_CLIENT = MongoClient(os.getenv('VIP_MONGO_URI'))
VIP_DB = VIP_CLIENT[os.getenv('VIP_DB_NAME')]


class WebhookProcessor:
    """Processes webhook data and saves to MongoDB"""

    def __init__(self, db, test_mode=False):
        self.db = db
        self.test_mode = test_mode
        self.conversations_collection = db['test_conversations' if test_mode else 'conversations']
        self.messages_collection = db['test_messages' if test_mode else 'messages']
        self.contacts_collection = db['test_contacts' if test_mode else 'contacts']

    def extract_media_type(self, message_data):
        """Extract media type from message"""
        msg = message_data.get('message', {})
        msg_type = msg.get('type', 'text')

        if msg_type == 'attachment':
            # For attachment type, get the nested attachment type
            attachment = msg.get('attachment', {})
            return attachment.get('type', 'file')
        elif msg_type in ['image', 'video', 'document', 'file', 'audio']:
            return msg_type
        elif msg_type == 'media':
            return 'media'
        return None

    def process_webhook(self, webhook_data, traffic_type):
        """Process incoming webhook data"""
        try:
            if self.test_mode:
                logger.info("=" * 80)
                logger.info(f"TEST MODE - {traffic_type.upper()} WEBHOOK RECEIVED")
                logger.info("=" * 80)
                logger.info(json.dumps(webhook_data, indent=2))
                logger.info("=" * 80)

            contact = webhook_data.get('contact', {})
            message = webhook_data.get('message', {})
            channel = webhook_data.get('channel', {})
            event_type = webhook_data.get('event_type')

            # Extract phone number (use as chat_id for consistency)
            phone = contact.get('phone', '')
            contact_id = contact.get('id')

            if not phone and not contact_id:
                logger.error("No phone or contact_id found in webhook")
                return False

            # Use phone as primary identifier, fallback to contact_id
            chat_id = phone if phone else str(contact_id)

            # Extract message details
            message_id = message.get('messageId')
            channel_message_id = message.get('channelMessageId')
            timestamp = message.get('timestamp')
            message_content = message.get('message', {})
            message_type = message_content.get('type', 'text')

            # Determine sender based on traffic type
            if traffic_type == 'incoming':
                sender = chat_id
                sender_info = {
                    'phone': phone,
                    'contact_id': contact_id,
                    'name': f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
                }
            else:  # outgoing
                user = webhook_data.get('user')
                source = webhook_data.get('source', 'system')

                if user and isinstance(user, dict):
                    # Regular user message
                    sender = user.get('email', 'system')
                    sender_info = {
                        'id': user.get('id'),
                        'email': user.get('email'),
                        'firstName': user.get('firstName'),
                        'lastName': user.get('lastName'),
                        'role': user.get('role')
                    }
                else:
                    # Echo message or system message
                    sender = source
                    sender_info = {
                        'source': source
                    }

            # Save or update message
            message_doc = {
                '_id': str(message_id) if message_id else None,
                'chat_id': chat_id,
                'ts': datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now(),
                'sender': sender,
                'sender_info': sender_info,
                'type': message_type,
                'message_type': traffic_type,
                # Additional respond.io fields
                'channel_message_id': channel_message_id,
                'contact_id': contact_id,
                'channel_id': channel.get('id'),
                'channel_name': channel.get('name'),
                'channel_source': channel.get('source'),
                'status': message.get('status', []),
                'event_type': event_type,
                'event_id': webhook_data.get('event_id'),
                'source': webhook_data.get('source'),
                'created_at': datetime.now(),
                'raw_message': message_content  # Store full message object including text, attachments, etc.
            }

            # Add message tag if present
            if 'messageTag' in message_content:
                message_doc['message_tag'] = message_content['messageTag']

            # Handle different message types
            if message_type == 'attachment':
                # Handle attachment type with nested attachment object
                attachment = message_content.get('attachment', {})
                attachment_type = attachment.get('type', 'file')
                message_doc['attachment'] = {
                    'type': attachment_type,
                    'url': attachment.get('url'),
                    'fileName': attachment.get('fileName'),
                    'mimeType': attachment.get('mimeType'),
                    'size': attachment.get('size'),
                    'ext': attachment.get('ext'),
                    'description': attachment.get('description', '')
                }
            elif message_type == 'image' and 'url' in message_content:
                message_doc['image_url'] = message_content['url']
            elif message_type == 'video' and 'url' in message_content:
                message_doc['video_url'] = message_content['url']
            elif message_type == 'document' and 'url' in message_content:
                message_doc['document_url'] = message_content['url']
                if 'filename' in message_content:
                    message_doc['filename'] = message_content['filename']
            elif message_type == 'audio' and 'url' in message_content:
                message_doc['audio_url'] = message_content['url']
            elif message_type == 'location':
                message_doc['location'] = {
                    'latitude': message_content.get('latitude'),
                    'longitude': message_content.get('longitude'),
                    'address': message_content.get('address')
                }

            # Insert or update message
            if message_doc['_id']:
                result = self.messages_collection.update_one(
                    {'_id': message_doc['_id']},
                    {'$set': message_doc},
                    upsert=True
                )
                logger.info(f"Message upserted: {message_id} (matched: {result.matched_count}, modified: {result.modified_count}, upserted_id: {result.upserted_id})")
            else:
                message_doc.pop('_id')
                result = self.messages_collection.insert_one(message_doc)
                logger.info(f"Message inserted with _id: {result.inserted_id}")

            logger.info(f"Message saved: {message_id} for chat {chat_id}")

            if self.test_mode:
                logger.info(f"Saved to collection: {self.messages_collection.name}")
                logger.info(f"Database: {self.db.name}")

            # Extract actual media type for conversation tracking
            media_type = self.extract_media_type(message)

            # Update or create conversation
            self.update_conversation(
                chat_id=chat_id,
                contact=contact,
                channel=channel,
                message=message,
                media_type=media_type,
                timestamp=timestamp
            )

            return True

        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
            if self.test_mode:
                logger.error(f"Failed webhook data: {json.dumps(webhook_data, indent=2)}")
            return False

    def update_conversation(self, chat_id, contact, channel, message, media_type, timestamp):
        """Update or create conversation record"""
        try:
            ts_datetime = datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now()

            # Get existing conversation or create new structure
            existing = self.conversations_collection.find_one({'_id': chat_id})

            if existing:
                # Update existing conversation
                update_doc = {
                    'updated_at': datetime.now(),
                    'last_message_ts': ts_datetime
                }

                # Increment message count
                current_count = existing.get('message_count', 0)
                update_doc['message_count'] = current_count + 1

                # Update media counts using extracted media_type
                media_counts = existing.get('media_counts', {})
                if media_type:
                    media_counts[media_type] = media_counts.get(media_type, 0) + 1
                    update_doc['media_counts'] = media_counts

                # Update channel list (add if not present)
                channel_name = channel.get('name')
                if channel_name:
                    channels = existing.get('channel', [])
                    if channel_name not in channels:
                        channels.append(channel_name)
                    update_doc['channel'] = channels

                # Update contact information
                update_doc['contact'] = {
                    'id': contact.get('id'),
                    'firstName': contact.get('firstName'),
                    'lastName': contact.get('lastName'),
                    'email': contact.get('email'),
                    'phone': contact.get('phone'),
                    'language': contact.get('language'),
                    'profilePic': contact.get('profilePic'),
                    'countryCode': contact.get('countryCode'),
                    'status': contact.get('status')
                }

                # Update assignee if present
                if 'assignee' in contact:
                    update_doc['assignee'] = contact['assignee']

                result = self.conversations_collection.update_one(
                    {'_id': chat_id},
                    {'$set': update_doc}
                )
                if self.test_mode:
                    logger.info(f"Conversation updated: matched={result.matched_count}, modified={result.modified_count}")
            else:
                # Create new conversation
                conversation_doc = {
                    '_id': chat_id,
                    'created_at': datetime.now(),
                    'first_message_ts': ts_datetime,
                    'last_message_ts': ts_datetime,
                    'message_count': 1,
                    'media_counts': {},
                    'updated_at': datetime.now(),
                    'channel': [channel.get('name')] if channel.get('name') else [],
                    'contact': {
                        'id': contact.get('id'),
                        'firstName': contact.get('firstName'),
                        'lastName': contact.get('lastName'),
                        'email': contact.get('email'),
                        'phone': contact.get('phone'),
                        'language': contact.get('language'),
                        'profilePic': contact.get('profilePic'),
                        'countryCode': contact.get('countryCode'),
                        'status': contact.get('status')
                    },
                    'channel_info': {
                        'id': channel.get('id'),
                        'name': channel.get('name'),
                        'source': channel.get('source'),
                        'lastMessageTime': channel.get('lastMessageTime'),
                        'lastIncomingMessageTime': channel.get('lastIncomingMessageTime')
                    }
                }

                # Add assignee if present
                if 'assignee' in contact:
                    conversation_doc['assignee'] = contact['assignee']

                # Initialize media count if applicable using media_type
                if media_type:
                    conversation_doc['media_counts'][media_type] = 1

                result = self.conversations_collection.insert_one(conversation_doc)
                if self.test_mode:
                    logger.info(f"New conversation created with _id: {result.inserted_id}")

            logger.info(f"Conversation updated: {chat_id}")

            if self.test_mode:
                logger.info(f"Saved to collection: {self.conversations_collection.name}")
                logger.info(f"Database: {self.db.name}")

        except Exception as e:
            logger.error(f"Error updating conversation: {str(e)}", exc_info=True)

    def process_lifecycle_update(self, webhook_data):
        """Process contact lifecycle update webhook"""
        try:
            if self.test_mode:
                logger.info("=" * 80)
                logger.info("TEST MODE - LIFECYCLE UPDATE WEBHOOK RECEIVED")
                logger.info("=" * 80)
                logger.info(json.dumps(webhook_data, indent=2))
                logger.info("=" * 80)

            contact = webhook_data.get('contact', {})
            contact_id = contact.get('id')
            phone = contact.get('phone', '')
            lifecycle = webhook_data.get('lifecycle')
            old_lifecycle = webhook_data.get('oldLifecycle')
            event_type = webhook_data.get('event_type')
            event_id = webhook_data.get('event_id')

            if not contact_id and not phone:
                logger.error("No contact_id or phone found in lifecycle webhook")
                return False

            # Use phone as primary identifier, fallback to contact_id
            chat_id = phone if phone else str(contact_id)

            # Update contact record
            contact_doc = {
                '_id': str(contact_id),
                'phone': phone,
                'firstName': contact.get('firstName'),
                'lastName': contact.get('lastName'),
                'email': contact.get('email'),
                'language': contact.get('language'),
                'profilePic': contact.get('profilePic'),
                'countryCode': contact.get('countryCode'),
                'status': contact.get('status'),
                'lifecycle': lifecycle,
                'tags': contact.get('tags', []),
                'updated_at': datetime.now()
            }

            # Add assignee if present
            if 'assignee' in contact:
                contact_doc['assignee'] = contact['assignee']

            # Add lifecycle history
            lifecycle_change = {
                'from': old_lifecycle,
                'to': lifecycle,
                'timestamp': datetime.now(),
                'event_id': event_id
            }

            # Upsert contact with lifecycle history
            self.contacts_collection.update_one(
                {'_id': contact_doc['_id']},
                {
                    '$set': contact_doc,
                    '$push': {'lifecycle_history': lifecycle_change}
                },
                upsert=True
            )

            logger.info(f"Contact lifecycle updated: {contact_id} - {old_lifecycle} → {lifecycle}")

            # Also update the conversation record if it exists
            conversation_update = {
                'contact.lifecycle': lifecycle,
                'updated_at': datetime.now()
            }

            result = self.conversations_collection.update_one(
                {'_id': chat_id},
                {'$set': conversation_update}
            )

            if result.matched_count > 0:
                logger.info(f"Conversation lifecycle updated: {chat_id}")
                logger.info(f"MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}")
                if self.test_mode:
                    # Verify the update
                    updated_doc = self.conversations_collection.find_one({'_id': chat_id})
                    logger.info(f"Verified contact.lifecycle in DB: {updated_doc.get('contact', {}).get('lifecycle', 'NOT FOUND')}")
            else:
                logger.info(f"No conversation found for contact: {chat_id}")

            if self.test_mode:
                logger.info(f"Saved to collection: {self.contacts_collection.name}")
                logger.info(f"Database: {self.db.name}")

            return True

        except Exception as e:
            logger.error(f"Error processing lifecycle update: {str(e)}", exc_info=True)
            if self.test_mode:
                logger.error(f"Failed webhook data: {json.dumps(webhook_data, indent=2)}")
            return False


# Initialize processors
faster_processor = WebhookProcessor(FASTER_DB, test_mode=TEST_MODE)
vip_processor = WebhookProcessor(VIP_DB, test_mode=TEST_MODE)


# Webhook endpoints
@app.route('/webhook/faster/incoming', methods=['POST'])
def faster_incoming():
    """Handle incoming messages for Faster AI"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        success = faster_processor.process_webhook(data, 'incoming')

        if success:
            return jsonify({'status': 'success', 'message': 'Webhook processed'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Processing failed'}), 500

    except Exception as e:
        logger.error(f"Error in faster_incoming endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/faster/outgoing', methods=['POST'])
def faster_outgoing():
    """Handle outgoing messages for Faster AI"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        success = faster_processor.process_webhook(data, 'outgoing')

        if success:
            return jsonify({'status': 'success', 'message': 'Webhook processed'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Processing failed'}), 500

    except Exception as e:
        logger.error(f"Error in faster_outgoing endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/vip/incoming', methods=['POST'])
def vip_incoming():
    """Handle incoming messages for VIP"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        success = vip_processor.process_webhook(data, 'incoming')

        if success:
            return jsonify({'status': 'success', 'message': 'Webhook processed'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Processing failed'}), 500

    except Exception as e:
        logger.error(f"Error in vip_incoming endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/vip/outgoing', methods=['POST'])
def vip_outgoing():
    """Handle outgoing messages for VIP"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        success = vip_processor.process_webhook(data, 'outgoing')

        if success:
            return jsonify({'status': 'success', 'message': 'Webhook processed'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Processing failed'}), 500

    except Exception as e:
        logger.error(f"Error in vip_outgoing endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/faster/lifecycle', methods=['POST'])
def faster_lifecycle():
    """Handle contact lifecycle updates for Faster AI"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Check if it's a lifecycle update event
        event_type = data.get('event_type')
        if event_type != 'contact.lifecycle.updated':
            return jsonify({'error': 'Invalid event type', 'expected': 'contact.lifecycle.updated'}), 400

        success = faster_processor.process_lifecycle_update(data)

        if success:
            return jsonify({'status': 'success', 'message': 'Lifecycle update processed'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Processing failed'}), 500

    except Exception as e:
        logger.error(f"Error in faster_lifecycle endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/vip/lifecycle', methods=['POST'])
def vip_lifecycle():
    """Handle contact lifecycle updates for VIP"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Check if it's a lifecycle update event
        event_type = data.get('event_type')
        if event_type != 'contact.lifecycle.updated':
            return jsonify({'error': 'Invalid event type', 'expected': 'contact.lifecycle.updated'}), 400

        success = vip_processor.process_lifecycle_update(data)

        if success:
            return jsonify({'status': 'success', 'message': 'Lifecycle update processed'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Processing failed'}), 500

    except Exception as e:
        logger.error(f"Error in vip_lifecycle endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'test_mode': TEST_MODE,
        'endpoints': {
            'faster_incoming': '/webhook/faster/incoming',
            'faster_outgoing': '/webhook/faster/outgoing',
            'faster_lifecycle': '/webhook/faster/lifecycle',
            'vip_incoming': '/webhook/vip/incoming',
            'vip_outgoing': '/webhook/vip/outgoing',
            'vip_lifecycle': '/webhook/vip/lifecycle'
        }
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API information"""
    return jsonify({
        'service': 'Respond.io Webhook Bridge',
        'version': '1.0.0',
        'test_mode': TEST_MODE,
        'documentation': {
            'faster_incoming': 'POST /webhook/faster/incoming',
            'faster_outgoing': 'POST /webhook/faster/outgoing',
            'faster_lifecycle': 'POST /webhook/faster/lifecycle',
            'vip_incoming': 'POST /webhook/vip/incoming',
            'vip_outgoing': 'POST /webhook/vip/outgoing',
            'vip_lifecycle': 'POST /webhook/vip/lifecycle',
            'health': 'GET /health'
        }
    }), 200


if __name__ == '__main__':
    logger.info(f"Starting Flask application on port {PORT}")
    logger.info(f"Test mode: {TEST_MODE}")
    logger.info(f"Endpoints available:")
    logger.info(f"  - POST /webhook/faster/incoming")
    logger.info(f"  - POST /webhook/faster/outgoing")
    logger.info(f"  - POST /webhook/faster/lifecycle")
    logger.info(f"  - POST /webhook/vip/incoming")
    logger.info(f"  - POST /webhook/vip/outgoing")
    logger.info(f"  - POST /webhook/vip/lifecycle")
    logger.info(f"  - GET /health")

    app.run(host='0.0.0.0', port=PORT, debug=(os.getenv('FLASK_ENV') == 'development'))
