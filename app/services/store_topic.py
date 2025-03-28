import boto3
import uuid
import json
from fastapi import HTTPException
import time

# from models.store_topic import CATEGORIES, DIFFICULTY_LEVELS, TopicRequest

CATEGORIES = ["Technical & Programming", "Mathematics and Algorithms", "Science & Engineering", "History & Social Studies", "Creative Writing & Literature", "Health & Medicine"]
DIFFICULTY_LEVELS = ["BEGINNER", "INTERMEDIATE", "ADVANCED"]

# Initialize client
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
lambda_client = boto3.client("lambda", region_name="us-east-1")
sqs = boto3.client("sqs", region_name="us-east-1")
stepfunctions = boto3.client('stepfunctions', region_name="us-east-1")

topics_table = dynamodb.Table("EPTopicsRequest")
status_table = dynamodb.Table("EPPodcastStatus")

SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/184226036469/EchoPodQueue"
STEP_FUNCTION_ARN = "arn:aws:states:us-east-1:184226036469:stateMachine:PodcastGenerationWorkflow"



# Define category-specific Lambda functions
CATEGORY_LAMBDAS = {
    "Technical & Programming": "EPTechProgramming",
    "Mathematics and Algorithms": "lambda_math_algorithms",
    "Science & Engineering": "lambda_science_engineering",
    "History & Social Studies": "lambda_history_social",
    "Creative Writing & Literature": "lambda_creative_writing",
    "Health & Medicine": "lambda_health_medicine"
}

def lambda_handler(event, context):
    """
    sumary_line

    Keyword arguments:
    argument -- description
    Return: return_description
    """
    
    if "body" in event: request = json.loads(event["body"])
    else: request = event
    
    # Validate request parameters
    validate_request(request)
    
    # Generate unique IDs
    topic_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    timestamp = str(int(time.time()))
    
    # Store request in DynamoDB
    store_request(request, topic_id, request_id, timestamp)
    
    # Start Step Functions execution
    start_step_function(request, topic_id, request_id)
    
    # Return success response
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "message": "Podcast generation started successfully",
            "topic_id": topic_id,
            "request_id": request_id,
            "status": "PROCESSING"
        })
    }

        

def validate_request(request):  
    # validate cateogry
    if request["category"] not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category. Choose from: " + ", ".join(CATEGORIES))
    
    # validate difficulty level
    if request["level_of_difficulty"] not in DIFFICULTY_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid difficulty level. Choose from: " + ", ".join(DIFFICULTY_LEVELS))
    
    # validate chapters
    if request["chapters"] <= 0:
        raise HTTPException(status_code=400, detail="Chapters must be a positive integer")
    

def store_request(request, topic_id, request_id, timestamp):
    
    topics_table.put_item(Item={
        "request_id": request_id,
        "topic_id": topic_id,
        "category": request["category"],
        "topic": request["topic"],
        "desc": request["desc"],
        "level_of_difficulty": request["level_of_difficulty"],
        "chapters": request["chapters"],
        "status": "PENDING",
        "timestamp": str(time.time())
    })
    
    # Initialize status in status table
    status_table.put_item(Item={
        "topic_id": topic_id,
        "status": "CONTENT_GENERATION_STARTED",
        "intro_complete": False,
        "chapters_complete": {},
        "audio_complete": {},
        "created_at": timestamp,
        "updated_at": timestamp
    })
    
def start_step_function(request, topic_id, request_id):
    """Starts Step Functions workflow"""
    # Prepare input for Step Functions
    workflow_input = {
        "topic_id": topic_id,
        "request_id": request_id,
        "topic": request["topic"],
        "desc": request["desc"],
        "level_of_difficulty": request["level_of_difficulty"],
        "chapters": request["chapters"],
        "category": request["category"]
    }
    
    # Start Step Functions execution
    stepfunctions.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN,
        name=f"podcast-{topic_id}",
        input=json.dumps(workflow_input)
    )
    
# zip function.zip store_topic.py
# aws lambda update-function-code \
#     --function-name EPStoreTopic \
#     --zip-file fileb://function.zip \
#     --region us-east-1