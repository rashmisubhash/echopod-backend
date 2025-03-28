import boto3
import json
import time
from botocore.exceptions import ClientError

# Initialize AWS clients
polly = boto3.client("polly", region_name = "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name = "us-east-1")
status_table = dynamodb.Table("EPPodcastStatus")

def lambda_handler(event, context):
    """
    Checks the status of all Polly tasks for a given topic.
    Called by Step Functions while waiting for audio generation to complete.
    """
    
    print("Received event:", json.dumps(event))
    
    # If event is a string, parse it
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError:
            raise Exception("Invalid JSON string passed to Lambda")

    # If event is a list (e.g., from "$[0]"), get the first item
    if isinstance(event, list):
        event = event[0]  # or handle all items in a loop if needed

    # Now it's safe to call .get()
    topic_id = event.get("topic_id")
    print("Topic ID:", topic_id)

    
    # topic_id = event.get("topic_id")
    if not topic_id: raise ValueError("No topic_id provided in event")
    
    try:
        # Get the Polly tasks from DynamoDB
        response = status_table.get_item(
            Key = {"topic_id": topic_id}
        )
        
        if "Item" not in response: raise ValueError(f"No records found for the {topic_id}")
        
        item = response["Item"]
        if "polly_tasks" not in item: raise ValueError(f"No Polly tasks found for topic_id: {topic_id}")

        polly_tasks = item.get("polly_tasks", [])
        all_tasks_complete = True
        all_tasks_status = []
        print("these are the polly tasks", polly_tasks)
        
        # Check each task's status
        for task in polly_tasks:
            task_id = task.get("task_id")
            # Get current status from Polly
            try:
                task_response = polly.get_speech_synthesis_task(TaskId=task_id)
                task_status = task_response["SynthesisTask"]["TaskStatus"]
                
                # Update task status
                task["status"] = task_status
                
                # If any task is not complete, mark as still in progress
                if task_status != "completed":
                    if task_status == "failed":
                        print(f"Polly task {task_id} failed")
                    else:
                        print(f"Polly task {task_id} still in progress: {task_status}")
                    all_tasks_complete = False
                
            except ClientError as e:
                print(f"Error Check Polly task {task_id}: {str(e)}")
                task["status"] = "ERROR"
                all_tasks_complete = False
                
            all_tasks_status.append({
                "task_id": task_id,
                "content_type": task.get("content_type"),
                "chunk": task.get("chunk"),
                "status": task.get("status")
            })
            
        # Update DynamoDB with latest task statuses
        status_table.update_item(
            Key = {"topic_id": topic_id},
            UpdateExpression = "SET polly_tasks_status = :status, updated_at = :updated_at",
            ExpressionAttributeValues = {
                ":status": all_tasks_status,
                ":updated_at": str(int(time.time()))
            }
        )
        
        # Update podcast status based on completion
        if all_tasks_complete: update_status(topic_id, "AUDIO_GENERATED")
        
        return {
            "topic_id": topic_id,
            "allTasksComplete": all_tasks_complete,
            "taskStatuses": all_tasks_status
        }
        
    except Exception as e:
        print(f"Error checking Polly tasks: {str(e)}")
        # Don't update status to failed here as this function will be retried
        return {
            "topic_id": topic_id,
            "allTasksComplete": False,
            "error": str(e)
        }
        
def update_status(topic_id, status):
    """Update pocast status in DynamoDB"""
    status_table.update_item(
        Key = {"topic_id": topic_id},
        UpdateExpression = "SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames = {"#status": "status"},
        ExpressionAttributeValues = {
            ":status": status,
            ":updated_at": str(int(time.time()))
        }
    )

# zip function.zip polly_status_checker.py
# aws lambda update-function-code \
#     --function-name EPPollyStatusChecker \
#     --zip-file fileb://function.zip \
#     --region us-east-1
        