import boto3
import os
import json

s3 = boto3.client("s3", region_name="us-east-1")
CONTENT_BUCKET = "echopod-content"

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    
    topic_id = event.get("topic_id")
    if not topic_id:
        raise ValueError("Missing 'topic_id' in input")
    
    try:
        # List all files under the topic_id folder
        response = s3.list_objects_v2(
            Bucket=CONTENT_BUCKET,
            Prefix=f"{topic_id}/"
        )
        
        if "Contents" not in response:
            raise Exception(f"No files found under topic: {topic_id}")

        chapter_keys = []
        files = []
        
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.endswith(".json"):
                files.append(key)
                filename = os.path.basename(key)
                chapter_key = filename.split(".")[0]  # intro.json → intro
                chapter_keys.append(chapter_key)
        
        return {
            "statusCode": 200,
            "topic_id": topic_id,
            "files": files,
            "chapter_keys": chapter_keys
        }
    
    except Exception as e:
        print(f"Error listing content files: {str(e)}")
        return {
            "statusCode": 500,
            "error": str(e),
            "topic_id": topic_id
        }

# zip function.zip content_file_lister.py
# aws lambda update-function-code \
#     --function-name EPContentFileLister \
#     --zip-file fileb://function.zip \
#     --region us-east-1