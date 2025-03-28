import boto3
import uuid
import json
from fastapi import HTTPException
import time

# from models.store_topic import CATEGORIES, DIFFICULTY_LEVELS, TopicRequest

CATEGORIES = ["Technical & Programming", "Mathematics and Algorithms", "Science & Engineering", "History & Social Studies", "Creative Writing & Literature", "Health & Medicine"]
DIFFICULTY_LEVELS = ["BEGINNER", "INTERMEDIATE", "ADVANCED"]

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("EPTopicsRequest")
SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/184226036469/EchoPodQueue"

lambda_client = boto3.client("lambda", region_name="us-east-1")
sqs = boto3.client("sqs", region_name="us-east-1")

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
        
    
    # validate cateogry
    if request["category"] not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category. Choose from: " + ", ".join(CATEGORIES))
    
    # validate difficulty level
    if request["level_of_difficulty"] not in DIFFICULTY_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid difficulty level. Choose from: " + ", ".join(DIFFICULTY_LEVELS))
    
    # validate chapters
    if request["chapters"] <= 0:
        raise HTTPException(status_code=400, detail="Chapters must be a positive integer")
    
    topic_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    
    user_input = {
        "topic_id": topic_id,
        "category": request["category"],
        "topic": request["topic"],
        "desc": request["desc"],
        "level_of_difficulty": request["level_of_difficulty"],
        "chapters": request["chapters"],
    }
    
    table.put_item(Item={
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
    
    # # Public message to SQS for content generation
    # sqs.send_message(
    #     QueueUrl = SQS_QUEUE_URL,
    #     MessageBody = json.dumps({
    #         "request_id": request_id,
    #         "user_input": user_input
    #     })
    # )
    
    # Call Category specific lambda function
    lambda_name = CATEGORY_LAMBDAS.get(request["category"])
    if lambda_name:
        payload = {
            "topic_id": topic_id,
            "category": request["category"],
            "topic": request["topic"],
            "desc": request["desc"],
            "level_of_difficulty": request["level_of_difficulty"],
            "chapters": request["chapters"]
        }
        
        
        
        try: 
            lambda_client.invoke(
                FunctionName=lambda_name,
                InvocationType="Event",
                Payload=json.dumps(payload)
            )
            
    #         print(f"Invoked {lambda_name} asynchronously")
    #     except Exception as e:
    #         print(f" Error invoking {lambda_name}: {e} ")
            
        #     # ✅ Fix: Read and properly parse the response
        #     response_payload = response["Payload"].read().decode("utf-8")

        #     # ✅ Debugging: Print raw response
        #     print("DEBUG: Raw Lambda Response Payload:", response_payload)

        #     # ✅ Parse first layer of JSON
        #     try:
        #         parsed_response = json.loads(response_payload)
        #         print("DEBUG: Parsed Lambda Response:", parsed_response)
        #     except json.JSONDecodeError:
        #         return {
        #             "statusCode": 500,
        #             "message": "Invalid JSON response from Lambda",
        #             "response": response_payload
        #         }

        #     # ✅ Fix: Ensure `response` is correctly deserialized
        #     if "response" in parsed_response and isinstance(parsed_response["response"], str):
        #         try:
        #             parsed_response["response"] = json.loads(parsed_response["response"])
        #         except json.JSONDecodeError:
        #             print("WARNING: `response` field is not valid JSON!")
                    
        #     str_content = {
        #         "intro": parsed_response["response"].get("intro", "Introduction no generated"),
        #     }
            
        #     for i in range(1, request["chapters"] + 1):
        #         str_content[f"chapter_{i}"] = parsed_response["response"].get(f"chapter_{i}", f"chapter {i} not generated")

        #     return {
        #         "statusCode": 200, 
        #         "message": "Data Stored Successfully", 
        #         "topic_id": topic_id,
        #         "chapter_breakdown": str_content  # ✅ Fully formatted response
        #     }
        except Exception as e:
            return {
                "statusCode": 500,
                "message": "Error invoking",
                "error": str(e)
            }
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "request_id": request_id,
            "message": "Processing started..",
            "status": "PENDING"
        })
    }
    
# zip function.zip store_topic.py
# aws lambda update-function-code \
#     --function-name EPStoreTopic \
#     --zip-file fileb://function.zip \
#     --region us-east-1