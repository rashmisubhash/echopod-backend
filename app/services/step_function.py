{
  "StartAt": "ContentGeneration",
  "States": {
    "ContentGeneration": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:us-east-1:184226036469:function:EPTechProgramming",
        "Payload": {
          "topic_id.$": "$.topic_id",
          "topic.$": "$.topic",
          "desc.$": "$.desc",
          "level_of_difficulty.$": "$.level_of_difficulty",
          "chapters.$": "$.chapters",
          "category.$": "$.category"
        }
      },
      "Retry": [
        {
          "ErrorEquals": [
            "States.TaskFailed"
          ],
          "IntervalSeconds": 3,
          "MaxAttempts": 2,
          "BackoffRate": 1.5
        }
      ],
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Next": "HandleContentGenerationError"
        }
      ],
      "Next": "CheckContentGenerationStatus"
    },
    "CheckContentGenerationStatus": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.Payload.statusCode",
          "NumericEquals": 200,
          "Next": "BuildContentNotification"
        }
      ],
      "Default": "HandleContentGenerationError"
    },
    "BuildContentNotification": {
      "Type": "Pass",
      "Parameters": {
        "message": "Content generation completed successfully",
        "topic_id.$": "$.Payload.topic_id"
      },
      "ResultPath": "$.contentNotification",
      "Next": "NotifyContentGenerated"
    },
    "NotifyContentGenerated": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:184226036469:PodcastNotifications",
        "Message.$": "States.JsonToString($.contentNotification)",
        "Subject": "Content Generated Notification"
      },
      "ResultPath": "$.notificationResult",
      "Next": "GetContentFileKeys"
    },
    "HandleContentGenerationError": {
      "Type": "Fail",
      "Error": "ContentGenerationFailed",
      "Cause": "Content generation failed"
    },
    "GetContentFileKeys": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:us-east-1:184226036469:function:EPContentFileLister",
        "Payload": {
          "topic_id.$": "$.Payload.topic_id"
        }
      },
      "ResultPath": "$.fileKeys",
      "Next": "MergeFileKeys"
    },
    "MergeFileKeys": {
      "Type": "Pass",
      "Parameters": {
        "topic_id.$": "$.fileKeys.Payload.topic_id",
        "files.$": "$.fileKeys.Payload.files",
        "chapter_keys.$": "$.fileKeys.Payload.chapter_keys"
      },
      "ResultPath": "$",
      "Next": "GenerateAudioInParallel"
    },
    "GenerateAudioInParallel": {
      "Type": "Map",
      "ItemsPath": "$.files",
      "ResultPath": "$.audioGenerationResults",
      "Parameters": {
        "key.$": "$$.Map.Item.Value",
        "topic_id.$": "$.topic_id"
      },
      "Iterator": {
        "StartAt": "EPPolly",
        "States": {
          "EPPolly": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:us-east-1:184226036469:function:EPPolly",
            "End": true
          }
        }
      },
      "Next": "WaitForPolly"
    },
    "WaitForPolly": {
      "Type": "Wait",
      "Seconds": 60,
      "Next": "CheckPollyStatus"
    },
    "CheckPollyStatus": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:us-east-1:184226036469:function:EPPollyStatusChecker",
        "Payload": {
          "topic_id.$": "$.topic_id"
        }
      },
      "ResultPath": "$.statusCheck",
      "Next": "MergeStatusWithOriginal"
    },
    "MergeStatusWithOriginal": {
      "Type": "Pass",
      "Parameters": {
        "topic_id.$": "$.statusCheck.Payload.topic_id",
        "allTasksComplete.$": "$.statusCheck.Payload.allTasksComplete",
        "taskStatuses.$": "$.statusCheck.Payload.taskStatuses",
        "chapter_keys.$": "$.chapter_keys"
      },
      "ResultPath": "$.Payload",
      "Next": "IsPollyDone"
    },
    "IsPollyDone": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.Payload.allTasksComplete",
          "BooleanEquals": true,
          "Next": "BuildAudioNotification"
        }
      ],
      "Default": "WaitForPolly"
    },
    "BuildAudioNotification": {
      "Type": "Pass",
      "Parameters": {
        "notification": {
          "message": "Audio generation completed successfully",
          "topic_id.$": "$.Payload.topic_id"
        }
      },
      "ResultPath": "$.audioNotification",
      "Next": "NotifyAudioGenerated"
    },
    "NotifyAudioGenerated": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:184226036469:PodcastNotifications",
        "Message.$": "States.JsonToString($.audioNotification.notification)",
        "Subject": "Audio Generated Notification"
      },
      "ResultPath": "$.audioNotificationResult",
      "Next": "CompressChaptersInParallel"
    },
    "CompressChaptersInParallel": {
      "Type": "Map",
      "ItemsPath": "$.Payload.chapter_keys",
      "Parameters": {
        "chapter_key.$": "$$.Map.Item.Value",
        "topic_id.$": "$.Payload.topic_id"
      },
      "Iterator": {
        "StartAt": "EPAudioFinalizer",
        "States": {
          "EPAudioFinalizer": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:us-east-1:184226036469:function:EPAudioFinalizer",
            "End": true
          }
        }
      },
      "Next": "BuildAudioCompressed"
    },
    "BuildAudioCompressed": {
      "Type": "Pass",
      "Parameters": {
        "notification": {
          "message": "Audio generation compressed successfully",
          "topic_id.$": "$.Payload.topic_id"
        }
      },
      "ResultPath": "$.audioNotification",
      "Next": "NotifyAudioCompressed"
    },
    "NotifyAudioCompressed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:184226036469:PodcastNotifications",
        "Message.$": "States.JsonToString($.notification.notification)",
        "Subject": "Audio Compressed Notification"
      },
      "ResultPath": null,
      "End": true
    }
  }
}