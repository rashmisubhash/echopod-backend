import json
import boto3
import logging
from boto3.dynamodb.conditions import Attr

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name="us-east-1")
table = dynamodb.Table('EPWebSocketConnections')

# Set your WebSocket API Gateway endpoint here
WEBSOCKET_ENDPOINT = "https://guf5dhj3gb.execute-api.us-east-1.amazonaws.com/dev"

def lambda_handler(event, context):
    try:
        logger.info(f"Received SNS event: {json.dumps(event)}")
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])

        message = sns_message.get('message', 'Default Notification')
        notification_type = sns_message.get('type', 'general')
        topic_id = sns_message.get('topic_id')

        if not topic_id:
            logger.warning("No topic_id found in SNS message.")
            return { 'statusCode': 400 }

        # Prepare payload to send
        payload = {
            'message': message,
            'type': notification_type,
            'topic_id': topic_id,
            'timestamp': context.get_remaining_time_in_millis()
        }

        # Filter connections by topic_id
        connections = table.scan(
            FilterExpression=Attr("topic_id").eq(topic_id)
        ).get('Items', [])

        logger.info(f"Sending notification to {len(connections)} clients subscribed to topic_id: {topic_id}")

        apigw_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=WEBSOCKET_ENDPOINT
        )

        for conn in connections:
            connection_id = conn['connectionId']
            try:
                apigw_client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps(payload).encode('utf-8')
                )
                logger.info(f"Notification sent to: {connection_id}")
            except Exception as e:
                logger.warning(f"Failed to send to {connection_id}: {e}")
                table.delete_item(Key={'connectionId': connection_id})

        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'success', 'targeted_clients': len(connections)})
        }

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'status': 'error', 'message': str(e)})
        }

# zip function.zip notification_service.py
# aws lambda update-function-code \
#     --function-name EPNotificationService \
#     --zip-file fileb://function.zip \
#     --region us-east-1   
