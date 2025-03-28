# echopod-backend

# 🎧 EchoPod Backend

EchoPod is an AI-powered personalized podcast generator that transforms user-submitted topics into custom, chapter-wise audio content in under 2 minutes. This backend powers the content generation, audio synthesis, and user management workflows using a serverless, event-driven architecture.

---

## 🚀 Overview

The EchoPod backend is built using **FastAPI**, **AWS Lambda**, **Amazon Bedrock**, **Amazon Polly**, **S3**, **Cognito**, and **EventBridge** to generate, store, and deliver AI-generated educational podcasts. It also supports speech-to-text input and real-time status updates.

---

## 🧠 Modules & Workflows

### 📚 Content Generation

- **POST /api/podcast/topic**  
  Accepts topic, tone, difficulty, and category; stores metadata in DynamoDB and triggers content generation Step Function.

- **Lambda: EPStoreTopic**  
  Initiates and logs podcast generation requests.

- **Lambda: EPTechProgramming / EPScience / EPMath**  
  Fetches chapter-wise content using Amazon Bedrock (Claude 3.5) based on the selected category. Stores chapter content in JSON format in S3.

---

### 🎙️ Audio Generation

- **Lambda: EPPolly**  
  Triggered via Step Function Map State to convert each chapter into MP3 audio using Amazon Polly. Runs parallel tasks and saves to S3.

- **Lambda: EPAudioFinalizer**  
  Combines audio parts (if applicable), compresses them, and prepares the final podcast file.

---

### 🗣️ Speech-to-Text & Personalization

- **POST /api/voice-to-text**  
  Accepts recorded voice input and returns the transcribed topic using Groq APIs.

- **POST /api/carbon-summary**  
  (Optional fun feature) Generates a carbon-emission equivalent if EchoPod is used instead of video learning.

---

### 🔐 Authentication

- **Cognito Integration**  
  - **/signup**, **/confirm**, **/signin** handled via Cognito user pool.
  - Access tokens are used to authenticate all protected API routes.

---

## 📦 Data Storage

- **DynamoDB**  
  Stores user profile, podcast metadata, and generation status.

- **S3**  
  Stores:
  - JSON content (chapter-wise breakdowns)
  - MP3 files (per chapter and final compressed audio)
  - Final podcast packages (ready for streaming)

---

## 🧩 Architecture Highlights

- 🛠 **Backend**: FastAPI + Python (deployed to AWS Lambda)
- 📊 **AI Models**: Amazon Bedrock (Claude 3.5), Amazon Polly, Groq API
- ☁️ **Infra**: Serverless (Lambda + API Gateway + EventBridge)
- 📦 **Storage**: Amazon S3 + DynamoDB
- 🔄 **Workflows**: AWS Step Functions for parallelized audio and compression tasks
- 🔐 **Auth**: Amazon Cognito (NetID-compatible for university integrations)

---

## 🧪 Future Endpoints

- `/api/podcast/playlist` – Build playlists from generated content  
- `/api/quiz` – Generate quiz questions based on chapters  
- `/api/favorites` – Save favorite chapters or podcasts  

---

## 📂 Folder Structure

