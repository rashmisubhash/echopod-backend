import boto3
import json
import time
import os
from botocore.exceptions import ClientError

# Initialize AWS Clients
s3 = boto3.client("s3", region_name = "us-east-1")
polly = boto3.client("polly", region_name = "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name = "us-east-1")
status_table = dynamodb.Table("EPPodcastStatus")

# S3 bucket configuration
CONTENT_BUCKET = "echopod-content"
AUDIO_BUCKET = "echopod-audio"

# Polly Configuration
DEFAULT_VOICE_ID = "Danielle"
DEFAULT_ENGINE = "neural"
DEFAULT_LANGUAGE = "en-US"

def lambda_handler(event, context):
    """
    Handles text to speech conversion for podcast content
    Called by Step Functions after content generation
    """
    
    print("Received event:", json.dumps(event))
    
    topic_id = event["topic_id"]
    
    # Update status in DynamoDB
    update_status(topic_id, "GENERATING_AUDIO")
    
    try:
        
        # Get list of content files from S3
        content_list = get_content_files(topic_id)
        
        # Process each content file
        tasks = []
        for content_file in content_list:
            file_key = content_file["Key"]
            file_name = os.path.basename(file_key)
            
            # Extract conetent type(intro or chapter_N)
            content_type = file_name.split('.')[0]
            
            # Get content
            content_obj = s3.get_object(Bucket =  CONTENT_BUCKET, Key=file_key)
            content_data = json.loads(content_obj["Body"].read().decode("utf-8"))
            
            # Extract text content
            text_content = content_data.get("content", "")
            
            # Process content for Polly (handle length limits)
            text_chunks = split_text_into_chunks(text_content)
            
            # Submit Polly tasks for each chunks
            chunks_tasks = process_polly_tasks(topic_id, content_type, text_chunks)
            tasks.append(chunks_tasks)
            
            # Mark audio as preocessing
            update_audio_status(topic_id, content_type, "PROCESSING")
            
        # Store tasks in DynamoDB for tracking
        store_polly_tasks(topic_id, tasks)
        
        return {
            "statusCode": 200, 
            "topic_id": topic_id,
            "message": "Audio generation started",
            "tasks": len(tasks),
            "allTasksComplete": all(
                t["status"] == "completed"
                for task_group in tasks
                for t in task_group
            )
        }
    
    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        update_status(topic_id, "AUDIO_GENERATION_FAILED")
        return {
            "statusCode": 500,
            "topic_id": topic_id,
            "error": str(e)
        }
        

def get_content_files(topic_id):
    """Get list of content files for a topic"""
    response = s3.list_objects_v2(
        Bucket = CONTENT_BUCKET,
        Prefix = f"{topic_id}/"
    )
    
    if "Contents" not in response:
        raise Exception(f"No content files found for topic {topic_id}")
    return response["Contents"]

def split_text_into_chunks(text, max_chars = 3000):
    """Split text into chunks for suitable Polly (respecting sentence boundaries)"""
    
    if len(text) <= max_chars: return [text]
    
    chunks = []
    sentences = text.replace("\n", " "). split(". ")
    # current_chunk = [] -- change
    current_chunk = ""
    
    for sentence in sentences:
        if not sentence.endswith("."): sentence += "."
        
        if len(current_chunk) + len(sentence) + 1 <= max_chars:
            if current_chunk: current_chunk += " "
            current_chunk += sentence
        else: 
            chunks.append(current_chunk)
            current_chunk = sentence
    
    if current_chunk: chunks.append(current_chunk)
    return chunks

def process_polly_tasks(topic_id, content_type, text_chunks):
    """Process text chunks with Polly"""
    tasks = []
    
    for i, chunk in enumerate(text_chunks):
        try:
            output_key = f"{topic_id}/{content_type}"
            if len(text_chunks) > 1: output_key += f"_part{i+1}"
            
            response = polly.start_speech_synthesis_task(
                Engine = DEFAULT_ENGINE,
                LanguageCode = DEFAULT_LANGUAGE,
                OutputFormat = "mp3",
                OutputS3BucketName = AUDIO_BUCKET,
                OutputS3KeyPrefix = output_key,
                Text = chunk,
                VoiceId = DEFAULT_VOICE_ID
            )
            
            task_id = response["SynthesisTask"]["TaskId"]
            tasks.append({
                "task_id": task_id,
                "content_type": content_type,
                "chunk": i,
                "status": response["SynthesisTask"]["TaskStatus"]
            })
            
            print(f"Started Polly task {task_id} for {content_type} chunk {i}")
            
            # Small delay to avoid throttling
            time.sleep(0.5)
        
        except Exception as e:
            print(f"Error starting Polly task for {content_type} chunk {i}: {str(e)}")
            raise
    return tasks

def store_polly_tasks(topic_id, tasks):
    """Store Polly task info in DynamoDB"""
    status_table.update_item (
        Key = {"topic_id": topic_id},
        UpdateExpression = "SET polly_tasks = :tasks, updated_at = :updated_at",
        ExpressionAttributeValues = {
            ":tasks": tasks,
            ":updated_at": str(int(time.time()))
        }
    )
        
def update_status(topic_id, status):
    """Update podcase status in DynamoDB"""
    status_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames = {"#status": status},
        ExpressionAttributeValues = {
            ":status": status,
            ":updated_at": str(int(time.time()))
        }
    )

def update_audio_status(topic_id, content_type, status):
    """Update audio generation status for a specific content"""
    status_table.update_item(
        Key = {"topic_id": topic_id},
        UpdateExpression = "SET audio_complete.#content_type = :status, updated_at = :updated_at",
        ExpressionAttributeNames = {"#content_type": content_type},
        ExpressionAttributeValues = {
            ":status": status,
            ":updated_at": str(int(time.time()))
        }
    ) 
    
# zip function.zip polly_convert.py
# aws lambda update-function-code \
#     --function-name EPPolly \
#     --zip-file fileb://function.zip \
#     --region us-east-1