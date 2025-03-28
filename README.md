# echopod-backend

# 🎧 EchoPod Backend

EchoPod is an AI-powered learning companion that turns any topic into a personalized, chapter-wise podcast in under 2 minutes.  
It generates structured educational content, converts it to audio using Amazon Polly, and delivers a seamless podcast experience — all powered by a fully serverless backend.

---

## ⚙️ Overview

This backend manages the entire generation pipeline via **a single API endpoint**, triggering an **AWS Step Function** to handle content generation, audio processing, and finalization.

---

## 🚀 Public API

### `POST /api/podcast/topic`

Initiates the full podcast generation process.

#### Request Body:
```json
{
  "topic": "Binary Trees",
  "category": "Technical & Programming",
  "tone": "Conversational",
  "difficulty": "Intermediate",
  "user_id": "netid123"
}
```

## 🧠 Step Function Workflow

The entire generation process is orchestrated using an **AWS Step Function** called `EchoPodGenerationFlow`. It executes the following Lambda functions in sequence and parallel:

---

### 1️⃣ `epstoretopic.py` – Initial Lambda
- Validates the incoming request from the `/api/podcast/topic` endpoint
- Stores the topic metadata in **DynamoDB**
- Triggers the next Lambda based on the selected **category**

---

### 2️⃣ `eptechprogramming.py` (or similar category-specific Lambda)
- Uses **Amazon Bedrock (Claude Sonnet 3.5)** to generate educational content
- Breaks the content into up to **7 structured chapters**
- Saves the chapter-wise JSON content into **Amazon S3**

---

### 3️⃣ `eppolly.py` – Audio Generation (Parallel)
- Triggered using **Step Function Map State**
- Converts each chapter to **MP3** using **Amazon Polly**
- Stores all MP3s in **S3**, organized by topic and chapter number

---

### 4️⃣ `epaudiofinalizer.py` – Finalization & Compression
- Compresses/merges MP3s (if chapters have multiple parts)
- Stores the **final podcast-ready MP3** in a public or private S3 location

---

### 5️⃣ `sendnotification.py` *(optional)*
- Publishes a **"podcast ready" event** to **Amazon EventBridge**
- Can trigger frontend notification, webhook, or email system


---

## 🧩 Architecture Highlights

- 🛠 **Backend**: FastAPI + Python (deployed to AWS Lambda)
- 📊 **AI Models**: Amazon Bedrock (Claude 3.5), Amazon Polly
- ☁️ **Infra**: Serverless (Lambda + API Gateway + SQS + Websockets + IAM + DynamoDB + Step Functions + S3)
- 📦 **Storage**: Amazon S3 + DynamoDB
- 🔄 **Workflows**: AWS Step Functions for parallelized audio and compression tasks
- 🔐 **Auth**: Amazon Cognito 

---

## 📦 Tech Stack Summary

| Layer             | Technology                                      |
|------------------|--------------------------------------------------|
| API Framework     | FastAPI (Python)                                 |
| Authentication    | Amazon Cognito                                   |
| Content Generation| Amazon Bedrock (Claude Sonnet 3.5)               |
| Text-to-Speech    | Amazon Polly                                     |
| Orchestration     | AWS Step Functions + Lambda                      |
| Data Storage      | Amazon S3 (audio + JSON), DynamoDB (metadata)    |
| Eventing & Logs   | Amazon EventBridge, CloudWatch, Boto3            |
| Hosting/API       | AWS Lambda + API Gateway                         |
| Dev Tools         | Uvicorn, Pydantic, Boto3, dotenv                 |

--

## 🧪 Future Endpoints

- `/api/podcast/playlist` – Build playlists from generated content  
- `/api/quiz` – Generate quiz questions based on chapters  
- `/api/favorites` – Save favorite chapters or podcasts  

---

