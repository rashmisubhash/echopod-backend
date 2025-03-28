import boto3
import json
import time
import random
from datetime import datetime

lambda_client = boto3.client("lambda", region_name="us-east-1")
sqs = boto3.client("sqs", region_name="us-east-1")

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
s3 = boto3.client('s3', region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
status_table = dynamodb.Table("EPPodcastStatus")

# S3 bucket for content storage
CONTENT_BUCKET = "echopod-content"


def generate_content(prompt, max_retries=8):
    retries = 0
    backoff_time = 2
    
    while retries < max_retries:
        try:
            time.sleep(0.5)
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt}
                        ]
                    }
                ],
                "max_tokens": 4096,
                "temperature": 0.5,
                "top_p": 0.999
            }

            response = bedrock.invoke_model(
                modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json"
            )
            
            # ✅ Debug: Log raw response
            print("DEBUG: Raw Bedrock Response:", response)

            
            # ✅ Fix: Read the response stream correctly
            # response_body = response["body"].read().decode("utf-8")  # 🔥 Properly read and decode StreamingBody
            
            response_body = response["body"].read().decode("utf-8")
            response_json = json.loads(response_body)
            return response_json.get("content", [{}])[0].get("text", "")
        
        except bedrock.exceptions.ThrottlingException as e:
            retries += 1
            wait_time = backoff_time * (2 ** retries) + random.uniform(0, 0.5)
            time.sleep(wait_time)
        
        except Exception as e:
            print(f"Error generating content: str{(e)}")
            return None
    
    print("Max retries reached")
    return None
    

def lambda_handler(event, context):
    
    """
    Handles content generation for tech & programming podcasts
    Called by Step Functions
    """
    print("Received event:", json.dumps(event))
    
    topic_id = event.get("topic_id")
    topic = event.get("topic")
    desc = event.get("desc")
    difficulty = event.get("level_of_difficulty")
    chapters = event.get("chapters")
    
    # Update status in DynamoDB
    update_status(topic_id, "GENERATING_INTRODUCTION")
    
    # Generate introduction and chapter outline
    intro_content = generate_introduction(topic, desc, difficulty, chapters)
    
    if not intro_content:
        update_status(topic_id, "FAILED")
        return {
            "statusCode": 500,
            "error": "Failed to generate introduction"
        }
    
    # Store introduction in S3
    s3.put_object(
        Bucket=CONTENT_BUCKET,
        Key=f"{topic_id}/intro.json",
        Body=json.dumps({"content": intro_content}),
        ContentType="application/json"
    )
    
    # Mark introduction as complete
    update_status(topic_id, "GENERATING_CHAPTERS", intro_complete=True)
    
    # Initialize conversation history for chapter generation
    conversation = [
        {"role": "user", "content": [{"type": "text", "text": get_intro_prompt(topic, desc, difficulty, chapters)}]},
        {"role": "assistant", "content": [{"type": "text", "text": intro_content}]}
    ]
    
    # Generate each chapter
    # all_chapters_complete = True
    for i in range(1, chapters + 1):
        update_status(topic_id, f"GENERATING_CHAPTER_{i}")
        
        chapter_prompt = get_chapter_prompt(i)
        conversation.append({"role": "user", "content": [{"type": "text", "text": chapter_prompt}]})
        
        # Generate chapter content
        chapter_content = generate_content_with_context(conversation)
        
        if not chapter_content:
            update_status(topic_id, "FAILED")
            return {
                "statusCode": 500,
                "error": f"Failed to generate chapter {i}"
            }
        
        # Add chapter content to conversation history
        conversation.append({"role": "assistant", "content": [{"type": "text", "text": chapter_content}]})
        
        # Store chapter in S3
        s3.put_object(
            Bucket=CONTENT_BUCKET,
            Key=f"{topic_id}/chapter_{i}.json",
            Body=json.dumps({"content": chapter_content}),
            ContentType="application/json"
        )
        
        # Mark chapter as complete
        update_chapter_status(topic_id, i, True)
        
        # Manage conversation context length if needed
        conversation = manage_conversation_context(conversation)
    
    # Update status to content generation complete
    update_status(topic_id, "CONTENT_GENERATION_COMPLETE")
    
    # Return success response
    return {
        "statusCode": 200,
        "topic_id": topic_id,
        "message": "Content generation complete",
        "next_step": "AUDIO_GENERATION"
    }
    
def get_chapter_prompt(chapter_number):
    """Creates the chapter prompt"""
    return f"""
    Write Chapter {chapter_number}:

    Please provide the complete content for this chapter that is optimized for AUDIO delivery:
    - Opening with a one-sentence recap
    - Detailed explanation using educational style
    - Describe all concepts verbally without relying on visual diagrams
    - Use audio-friendly analogies and descriptions that don't require visual aids
    - Include verbal cues like "first," "second," "moving on to," etc. to help listeners follow along
    - A smooth transition to the next chapter
    - 800-3000 words total

    IMPORTANT: Do NOT include any ASCII art, diagrams, or content that requires visual representation. All explanations must work in an audio-only format.
    """


def generate_content_with_context(conversation, max_retries=8):
    """Generate content using conversation history"""
    retries = 0
    backoff_time = 2
    
    while retries < max_retries:
        try:
            time.sleep(0.5)
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": conversation,
                "max_tokens": 4096,
                "temperature": 0.5,
                "top_p": 0.999
            }

            response = bedrock.invoke_model(
                modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json"
            )
            
            response_body = response["body"].read().decode("utf-8")
            response_json = json.loads(response_body)
            
            return response_json.get("content", [{}])[0].get("text", "")
        
        except bedrock.exceptions.ThrottlingException as e:
            retries += 1
            wait_time = backoff_time * (2 ** retries) + random.uniform(0, 0.5)
            print(f"Throttled. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        
        except Exception as e:
            print(f"Error generating content with context: {str(e)}")
            retries += 1
            if retries >= max_retries:
                break
            time.sleep(1)
    
    print("Max retries reached")
    return None
        
    

    
def generate_introduction(topic, desc, difficulty, chapters):
    """Generate introduction and chapter outline"""
    prompt = get_intro_prompt(topic, desc, difficulty, chapters)
    return generate_content(prompt)


def get_intro_prompt(topic, desc, difficulty, chapters):
    """Creates the introduction prompt"""
    return f"""
    Topic: {topic}
    Difficulty: {difficulty}
    Total Chapters: {chapters}
    Tone: EDUCATIONAL 
    Style: EDUCATIONAL 
    Format: PODCAST SCRIPT 
    Description: {desc}

    OUTPUT INSTRUCTIONS:

    ONLY create the introduction and chapter outline as specified below
    Do NOT write any chapter content yet
    Do NOT ask if I want you to continue
    Do NOT add any closing remarks
    Introduction: Write a 1-2 paragraph introduction to the topic that frames the discussion, peaks listener interest, and transitions into the chapter breakdown.

    Chapter Outline: Generate [X] chapter titles and 4-5 sentence summaries for each chapter. The chapters should build logically and cover key concepts for a [BEGINNER/INTERMEDIATE/ADVANCED] understanding.

    ===END OF INITIAL OUTPUT===

    After reviewing your introduction and outline, I will explicitly request specific chapters by saying "Write Chapter [Number]".
    """
    
def manage_conversation_context(conversation, max_messages=10):
    """Prevent conversation context from getting too large"""
    if len(conversation) <= max_messages: return conversation
    
    # Keep first two messages (intro prompt and response)
    important_context = conversation[:4]
    
    # Add a transition message
    important_context.append({
        "role": "user", 
        "content": [{"type": "text", "text": "Please continue with the next chapter in the same style."}]
    })
    
    # Add the most recent messages
    important_context.extend(conversation[-4:])
    
    return important_context
    
def update_status(topic_id, status, intro_complete = None):
    """Update podcast status in DynamoDB"""
    update_expression = "SET #status = :status, updated_at = :updated_at"
    expression_values = {
        ":status": status,
        ":updated_at": str(int(time.time()))
    }
    
    if intro_complete is not None:
        update_expression += ", intro_complete = :intro_complete"
        expression_values[":intro_complete"] = intro_complete
    
    status_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues=expression_values
    )
    
def update_chapter_status(topic_id, chapter_number, complete):
    """Update chapter completion status"""
    status_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression="SET chapters_complete.#chapter = :complete, updated_at = :updated_at",
        ExpressionAttributeNames={"#chapter": str(chapter_number)},
        ExpressionAttributeValues={
            ":complete": complete,
            ":updated_at": str(int(time.time()))
        }
    )

# zip function.zip lambda_tech_programming.py
# aws lambda update-function-code \
#     --function-name EPTechProgramming \
#     --zip-file fileb://function.zip \
#     --region us-east-1

    
    