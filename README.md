
---

# 🔐 JWT Authentication with OAuth2, RAG API, Celery & Redis

Seamless document upload and processing pipeline with FastAPI, JWT-based authentication, Redis, Celery, Qdrant (vector DB), and MongoDB.

---

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Mayankvanik/Rag_with_jwt_task.git
cd Rag_with_jwt_task
```

---

### 2. Setup Python Environment (using **uv**)

Make sure you have [uv](https://docs.astral.sh/uv/) installed.

```bash
uv init
uv sync   # Create & sync virtual environment
```

---

### 3. Run Redis Locally

Start Redis server:

```bash
sudo service redis-server start
```

---

### 4. Configure Qdrant (Vector Database)

* Create a free cluster at [Qdrant Cloud](https://qdrant.tech/).
* Copy your **API Key** and **Cluster URL**.

---

### 5. Setup MongoDB

* Install and run MongoDB locally
* Used for storing **user data & chat history**

---

### 6. Configure Environment Variables

Create a **`.env`** file in the root of your project (based on `sample.env`) and add your credentials:

```env
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_URL=your_qdrant_cluster_url
REDIS_URL=redis://localhost:6379/0
MONGO_URI=mongodb://localhost:27017
```

---

### 7. Start Celery Worker (Background Tasks)

Run Celery in a separate terminal to process file uploads:

```bash
celery -A app.services.celery_app worker --loglevel=info
```

---

### 8. Run the FastAPI Server

```bash
uv run -m app.main
```

---

### 9. Access API Docs

Swagger UI: 👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ✅ Notes

* `redis` is required for task queue: `REDIS_URL = redis://localhost:6379/0`
* Ensure **Qdrant** & **MongoDB** are configured correctly.
* Celery must be running in a separate terminal **before starting the main server**.


