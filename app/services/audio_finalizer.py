import boto3
import json
import time
import os
import subprocess
from collections import defaultdict

s3 = boto3.client("s3", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
status_table = dynamodb.Table("EPPodcastStatus")
topics_table = dynamodb.Table("EPTopicsRequest")

AUDIO_BUCKET = "echopod-audio"
TMP_DIR = "/tmp"

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    topic_id = event.get("topic_id")
    chapter_key = event.get("chapter_key")  # e.g., chapter_1 or intro
    if not topic_id or not chapter_key:
        raise ValueError("Missing topic_id or chapter_key")

    try:
        update_status(topic_id, "FINALIZING_AUDIO")

        audio_files = get_audio_files(topic_id, chapter_key)
        if len(audio_files) <= 1:
            print(f"Skipping compression for {chapter_key}: only one file")
            return {"status": "SKIPPED", "chapter_key": chapter_key}

        local_files = download_audio_files(audio_files)
        output_file = f"{TMP_DIR}/{chapter_key}_combined.mp3"
        combine_audio_files(local_files, output_file)

        combined_key = f"{topic_id}/{chapter_key}.mp3"
        s3.upload_file(output_file, AUDIO_BUCKET, combined_key)
        print(f"Uploaded: {combined_key}")
        
        # After uploading the combined file
        for key in audio_files:
            s3.delete_object(Bucket=AUDIO_BUCKET, Key=key)


        for f in local_files:
            if os.path.exists(f): os.remove(f)
        if os.path.exists(output_file): os.remove(output_file)
        
        update_status(topic_id, "COMPLETED")

        return {
            "status": "COMPLETED",
            "topic_id": topic_id,
            "chapter_key": chapter_key
        }
    except Exception as e:
        print(f"Error finalizing audio: {str(e)}")
        return {"status": "FAILED", "error": str(e)}

def get_audio_files(topic_id, chapter_key):
    response = s3.list_objects_v2(
        Bucket=AUDIO_BUCKET,
        Prefix=f"{topic_id}/{chapter_key}"
    )
    return [item["Key"] for item in response.get("Contents", []) if item["Key"].endswith(".mp3")]

def download_audio_files(keys):
    paths = []
    for key in keys:
        path = os.path.join(TMP_DIR, os.path.basename(key))
        s3.download_file(AUDIO_BUCKET, key, path)
        paths.append(path)
    return paths

def combine_audio_files(input_files, output_file):
    file_list_path = os.path.join(TMP_DIR, "filelist.txt")
    with open(file_list_path, 'w') as f:
        for file in input_files:
            f.write(f"file '{file}'\n")
    ffmpeg_path = '/opt/bin/ffmpeg' if os.path.exists('/opt/bin/ffmpeg') else '/usr/bin/ffmpeg'
    # ffmpeg_path = "/opt/ffmpeg" if os.path.exists("/opt/ffmpeg") else "/usr/bin/ffmpeg"
    subprocess.check_call([
        ffmpeg_path, "-f", "concat", "-safe", "0",
        "-i", file_list_path, "-c", "copy", output_file
    ])

def update_status(topic_id, status):
    status_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression="SET #status = :s, updated_at = :u",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":s": status,
            ":u": str(int(time.time()))
        }
    )
    
    topics_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression="SET #status = :s, updated_at = :u",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":s": status,
            ":u": str(int(time.time()))
        }
    )

# zip function.zip audio_finalizer.py
# aws lambda update-function-code \
#     --function-name EPAudioFinalizer \
#     --zip-file fileb://function.zip \
#     --region us-east-1