import boto3
import json
import time
import os
from botocore.exceptions import ClientError

s3 = boto3.client("s3", region_name="us-east-1")
polly = boto3.client("polly", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
status_table = dynamodb.Table("EPPodcastStatus")

CONTENT_BUCKET = "echopod-content"
AUDIO_BUCKET = "echopod-audio"
DEFAULT_VOICE_ID = "Danielle"
DEFAULT_ENGINE = "neural"
DEFAULT_LANGUAGE = "en-US"


def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    topic_id = event.get("topic_id")
    file_key = event.get("key")
    if not topic_id or not file_key:
        raise ValueError("Missing topic_id or key")

    try:
        file_name = os.path.basename(file_key)
        content_type = file_name.split('.')[0]

        obj = s3.get_object(Bucket=CONTENT_BUCKET, Key=file_key)
        content_data = json.loads(obj["Body"].read().decode("utf-8"))
        text_content = content_data.get("content", "")

        text_chunks = split_text_into_chunks(text_content)
        tasks = process_polly_tasks(topic_id, content_type, text_chunks)

        update_audio_status(topic_id, content_type, "PROCESSING")
        store_polly_tasks(topic_id, tasks)

        return {
            "statusCode": 200,
            "topic_id": topic_id,
            "content_type": content_type,
            "tasks": tasks
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"statusCode": 500, "error": str(e)}


def split_text_into_chunks(text, max_chars=3000):
    if len(text) <= max_chars:
        return [text]

    chunks, current_chunk = [], ""
    for sentence in text.replace("\n", " ").split(". "):
        if not sentence.endswith("."): sentence += "."
        if len(current_chunk) + len(sentence) + 1 <= max_chars:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            chunks.append(current_chunk)
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def process_polly_tasks(topic_id, content_type, text_chunks):
    tasks = []
    for i, chunk in enumerate(text_chunks):
        output_key = f"{topic_id}/{content_type}"
        if len(text_chunks) > 1:
            output_key += f"_part{i+1}"

        response = polly.start_speech_synthesis_task(
            Engine=DEFAULT_ENGINE,
            LanguageCode=DEFAULT_LANGUAGE,
            OutputFormat="mp3",
            OutputS3BucketName=AUDIO_BUCKET,
            OutputS3KeyPrefix=output_key,
            Text=chunk,
            VoiceId=DEFAULT_VOICE_ID
        )

        tasks.append({
            "task_id": response["SynthesisTask"]["TaskId"],
            "content_type": content_type,
            "chunk": i,
            "status": response["SynthesisTask"]["TaskStatus"]
        })
        time.sleep(0.5)
    return tasks


def store_polly_tasks(topic_id, tasks):
    status_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression="SET polly_tasks = list_append(if_not_exists(polly_tasks, :empty), :t), updated_at = :u",
        ExpressionAttributeValues={
            ":t": tasks,
            ":u": str(int(time.time())),
            ":empty": []
        }
    )


def update_audio_status(topic_id, content_type, status):
    status_table.update_item(
        Key={"topic_id": topic_id},
        UpdateExpression="SET audio_complete.#ct = :status, updated_at = :updated_at",
        ExpressionAttributeNames={"#ct": content_type},
        ExpressionAttributeValues={
            ":status": status,
            ":updated_at": str(int(time.time()))
        }
    )


# zip function.zip polly_convert.py
# aws lambda update-function-code \
#     --function-name EPPolly \
#     --zip-file fileb://function.zip \
#     --region us-east-1