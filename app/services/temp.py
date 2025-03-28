import boto3
import json
import time
import random

client = boto3.client("bedrock-runtime", region_name="us-east-1")
lambda_client = boto3.client("lambda", region_name="us-east-1")
sqs = boto3.client("sqs", region_name="us-east-1")

def generate_content(prompt, max_retries=5):
    retries = 0
    backoff_time = 1
    
    while retries < max_retries:
        try:
            
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

            response = client.invoke_model(
                modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json"
            )
            
            # ✅ Debug: Log raw response
            print("DEBUG: Raw Bedrock Response:", response)

            
            # ✅ Fix: Read the response stream correctly
            response_body = response["body"].read().decode("utf-8")  # 🔥 Properly read and decode StreamingBody

            # ✅ Debug: Print raw response (for debugging)
            print("DEBUG: Bedrock Response Body:", response_body)
            return response_body
        
        except client.exceptions.ThrottlingException as e:
            retries += 1
            wait_time = backoff_time * (2 ** retries) + random.uniform(0, 0.5)
            time.sleep(wait_time)
        
        except Exception as e:
            print(f"Error generating content: str{(e)}")
            return None
    
    print("Max retries reached")
    return None
    

def lambda_handler(event, context):

    for record in event["Records"]:
        body = json.loads(record["body"])
        request_id = body["request_id"]
        user_input = body["user_inputs"]
        
        intro_prompt = f"""
            Topic: {topic}
            Difficulty: {difficulty}
            Total Chapters: {chapters}
            Tone: EDUCATIONAL 
            Style:EDUCATIONAL 
            Format: PODCAST SCRIPT 
            Description: {desc}


            OUTPUT INSTRUCTIONS:

            ONLY create the introduction and chapter outline as specified below
            Do NOT write any chapter content yet
            Do NOT ask if I want you to continue
            Do NOT add any closing remarks
            Introduction: Write a 1-2 paragraph introduction to the topic that frames the discussion, peaks listener interest, and transitions into the chapter breakdown.


            Chapter Outline: Generate [X] chapter titles and 2-3 sentence summaries for each chapter. The chapters should build logically and cover key concepts for a [BEGINNER/INTERMEDIATE/ADVANCED] understanding.


            ===END OF INITIAL OUTPUT===


            After reviewing your introduction and outline, I will explicitly request specific chapters by saying "Write Chapter [Number]".
            """
            
        introduction = generate_content(intro_prompt)
    
    print(event)
    topic = event.get("topic")
    desc = event.get("desc")
    difficulty = event.get("level_of_difficulty")
    chapters = event.get("chapters")
    
    
    if not intro_response: 
        return {
            "statusCode": 500,
            "message": "Failed to generate introduuction and outline"
        }
    
    content = {
        "intro": intro_response
    }
    
    for i in range(1, chapters + 1):
        chapter_prompt = chapter_prompt = f"""
        Write Chapter {i}:

        Please provide the complete content for this chapter that is optimized for AUDIO delivery:
        - Opening with a one-sentence recap
        - Detailed explanation using [chosen style]
        - Describe all concepts verbally without relying on visual diagrams
        - Use audio-friendly analogies and descriptions that don't require visual aids
        - Include verbal cues like "first," "second," "moving on to," etc. to help listeners follow along
        - A smooth transition to the next chapter
        - 300-1000 words total

        IMPORTANT: Do NOT include any ASCII art, diagrams, or content that requires visual representation. All explanations must work in an audio-only format.
        """
        # f"Write Chapter {i}."
        
        print(f"Requesting chapter {i}...")
        chapter_content = generate_content(chapter_prompt)
        
        if chapter_content: content[f"chapter_{i}"] = chapter_content
        else: content[f"chapter_{i}"] = "Error retrieving chapter content."
        
        # time.sleep(2)
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Chapter content generated successfully",
            "response": content
        })
    }
    
    return {
        "statusCode": 200,
        "message": "Content generated successfully",
        "topic": topic,
        "response": content
    }

# zip function.zip lambda_tech_programming.py
# aws lambda update-function-code \
#     --function-name EPTechProgramming \
#     --zip-file fileb://function.zip \
#     --region us-east-1

    
    