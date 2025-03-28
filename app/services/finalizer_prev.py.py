import boto3
import json
import time
import os
import subprocess
from botocore.exceptions import ClientError
from collections import defaultdict

# Initialize AWS Clients
s3 = boto3.client("s3", region_name = "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name = "us-east-1")
status_table = dynamodb.Table("EPPodcastStatus")

# S3 bucket configuration
AUDIO_BUCKET = "echopod-audio"
PODCAST_BUCKET = "echopod-podcasts"

TMP_DIR = "/tmp"

def lambda_handler(event, context):
    """
    Finalized audio files by combining all Polly outputs into a single podcast.
    Called by Step Functions after all Polly tasks are complete
    """
    
    print("Received event:", json.dumps(event))
    
    topic_id = event.get("topic_id")
    if not topic_id: raise ValueError("No topic_id provided in event")
    
    try:
        # Update status
        update_status(topic_id, "FINALIZING_AUDIO")
        
        # Get the Polly tasks from DynamoDB
        response = status_table.get_item(
            Key = {"topic_id": topic_id}
        )
        
        if "Item" not in response: raise ValueError(f"No record found for topic_id: {topic_id}")

        item = response["Item"]
        podcast_meta = item.get("podcast_meta", {})
        
        # Get list of audio files from S3
        audio_files = get_audio_files(topic_id)
        if not audio_files: raise ValueError(f"No audio files found for topic_id: {topic_id}")
        
        # Download all audio files
        local_files = download_audio_files(audio_files)
        
        # Group files by chapter
        chapter_files = defaultdict(list)
        for file in local_files:
            filename = os.path.basename(file)
            if filename.startswith("intro"): chapter_key = "intro"
            elif filename.startswith("chapter"): chapter_key = "_".join(filename.split("_")[:2])
            chapter_files[chapter_key].append(file)
        
        # Sort files within each chapter group
        for key in chapter_files:
            chapter_files[key] = sorted(chapter_files[key])
        
        for chapter_key, files in chapter_files.items():
            output_file = f"{TMP_DIR}/{chapter_key}_combined.mp3"
            
            # combine files
            combine_audio_files(files, output_file)
            
            # Updload to same bucket under a new key
            combined_key = f"{topic_id}/{chapter_key}.mp3"
            s3.upload_file(output_file, AUDIO_BUCKET, combined_key)
            
            print(f"Uploaded combine dfile for {chapter_key} to {combined_key}")
            
            # cleanup
            for f in files:
                if os.path.exists(f): os.remove(f)
            if os.path.exists(output_file): os.remove(output_file)
            

        update_status(topic_id, "CHAPTER_AUDIO_FINALIZED")
        
        return {
            "topic_id": topic_id,
            "status": "CHAPTER_AUDIO_FINALIZED",
            "message": f"Chapters combined and uploaded successfully."
        }
    
    except Exception as e:
        print(f"Error finalized audio: {str(e)}")
        update_status(topic_id, "AUDIO_FINALIZATION_FAILED")
        return {
            "topic_id": topic_id,
            "status": "FAILED",
            "error": str(e)
        }

def get_audio_files(topic_id):
    """Get list of audio files form S3 for a topic"""
    try:
        response = s3.list_objects_v2(
            Bucket = AUDIO_BUCKET,
            Prefix = f"{topic_id}/"
        )
        
        if "Contents" not in response: return []
        
        return [
            {
                "key": item["Key"],
                "size": item ["Size"]
            }
            for item in response["Contents"]
            if item["Key"].endswith(".mp3")
        ]
    
    except Exception as e:
        print(f"Error getting audio files: {str(e)}")
        raise
    
def download_audio_files(files):
    """Download audio files from S3 to local tmp directory"""
    local_files = []
    for file in files:
        file_key = file["key"]
        local_path = os.path.join(TMP_DIR, os.path.basename(file_key))
        s3.download_file(AUDIO_BUCKET, file_key, local_path)
        local_files.append(local_path)
    return local_files

def combine_audio_files(input_files, output_file):
    """Combine multiple MP# files into a single file"""
    if os.path.exists("opt/ffmpeg") or os.path.exists("/usr/bin/ffmpeg"):
        file_list_path = os.path.join(TMP_DIR, "filelist.txt")
        with open(file_list_path, 'w') as f:
            for file in input_files:
                f.write(f"file '{file}'\n")
        try:
            ffmpeg_path = "/opt/ffmpeg" if os.path.exists("/opt/ffmpeg") else "/usr/bin/ffmpeg"
            subprocess.check_call([
                ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", file_list_path,
                "-c", "copy",
                output_file
            ])
            return
        except Exception as e:
            print(f"ffmpeg failed, falling back to basic concat: {str(e)}")
    
    # Fallback - simple concatenation
    with open(output_file, 'wb') as outfile:
        for file in input_files:
            with open(file, 'rb') as infile:
                outfile.write(infile.read())

def update_status(topic_id, status):
    """Update podcast status in DynamoDB"""
    status_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": status,
            ":updated_at": str(int(time.time()))
        }
    ) 
    
# zip function.zip audio_finalizer.py
# aws lambda update-function-code \
#     --function-name EPAudioFinalizer \
#     --zip-file fileb://function.zip \
#     --region us-east-1
            