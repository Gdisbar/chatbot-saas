# AI Chatbot SaaS Backend

A comprehensive, production-ready chatbot backend service built with FastAPI, featuring RAG capabilities, multi-LLM support, and advanced document processing.

## 🚀 Features

- **FastAPI Backend**: Asynchronous API server with automatic documentation
- **Multi-LLM Support**: OpenAI GPT-4, Anthropic Claude, Cohere integration
- **RAG System**: Retrieval-Augmented Generation with Weaviate vector database
- **Document Processing**: Support for PDFs, Excel, URLs, Docs, Notion, etc.
- **Conversational Memory**: Persistent chat history and context management
- **Advanced Flows**: LangGraph for complex conversational workflows
- **Scalable Architecture**: Docker-ready with cloud deployment options
- **Real-time Features**: WebSocket support for live chat
- **Authentication**: JWT-based user management
- **Rate Limiting**: Built-in API rate limiting and usage tracking

## 📁 Project Structure

```
chatbot-saas/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py              # Configuration and environment variables
│   ├── database.py            # Database connection and models
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── models.py          # User authentication models
│   │   ├── routes.py          # Authentication endpoints
│   │   └── utils.py           # JWT and password utilities
│   ├── chat/
│   │   ├── __init__.py
│   │   ├── models.py          # Chat-related database models
│   │   ├── routes.py          # Chat API endpoints
│   │   ├── websocket.py       # WebSocket handlers
│   │   └── services.py        # Chat business logic
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── providers.py       # LLM provider implementations
│   │   ├── chains.py          # LangChain conversation chains
│   │   └── graphs.py          # LangGraph workflow definitions
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embeddings.py      # Embedding generation
│   │   ├── vector_store.py    # Weaviate integration
│   │   └── retrieval.py       # Document retrieval logic
│   ├── document/
│   │   ├── __init__.py
│   │   ├── processors.py      # Document processing logic
│   │   ├── loaders.py         # File loaders for different formats
│   │   └── routes.py          # Document upload endpoints
│   └── utils/
│       ├── __init__.py
│       ├── rate_limiter.py    # Rate limiting utilities
│       └── logging.py         # Logging configuration
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_chat.py
│   ├── test_rag.py
│   └── test_documents.py
├── scripts/
│   ├── setup_db.py            # Database initialization
│   └── migrate.py             # Database migrations
├── frontend/                  # Optional React frontend
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── README.md
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
├── deployment/
│   ├── heroku.yml
│   ├── railway.toml
│   └── render.yaml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.9+
- PostgreSQL
- Redis
- Weaviate (Docker or Cloud)

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/chatbot-saas.git
cd chatbot-saas
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment setup**
```bash
cp .env.example .env
# Edit .env with your configurations
```

5. **Start services with Docker**
```bash
docker-compose up -d
```

6. **Initialize database**
```bash
python scripts/setup_db.py
```

7. **Run the application**
```bash
uvicorn app.main:app --reload
```

## ⚙️ Configuration

Create a `.env` file with the following variables:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/chatbot_db
REDIS_URL=redis://localhost:6379

# LLM Providers
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
COHERE_API_KEY=your_cohere_key

# Vector Database
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=your_weaviate_key

# Authentication
JWT_SECRET_KEY=your_jwt_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Environment
ENVIRONMENT=development
DEBUG=True
```

## 🔧 API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh access token

### Chat
- `POST /chat/conversations` - Create new conversation
- `GET /chat/conversations` - List user conversations
- `POST /chat/conversations/{id}/messages` - Send message
- `GET /chat/conversations/{id}/messages` - Get conversation history
- `WS /chat/ws/{conversation_id}` - WebSocket chat connection

### Documents
- `POST /documents/upload` - Upload document
- `POST /documents/url` - Process URL content
- `GET /documents` - List uploaded documents
- `DELETE /documents/{id}` - Delete document

### RAG
- `POST /rag/query` - Query knowledge base
- `GET /rag/similar` - Find similar documents

## 🏗️ Architecture

### Core Components

1. **FastAPI Server**: Asynchronous web framework handling HTTP requests and WebSocket connections
2. **LangChain Integration**: Manages LLM interactions, memory, and tool usage
3. **LangGraph Workflows**: Defines complex conversational flows and decision trees
4. **Vector Database**: Weaviate for efficient similarity search and RAG
5. **PostgreSQL**: Stores user data, chat history, and system configurations
6. **Redis**: Caching and session management

### Document Processing Pipeline

1. **File Upload**: Supports PDF, DOCX, Excel, CSV, TXT, and URLs
2. **Content Extraction**: Uses appropriate parsers for each file type
3. **Chunking**: Intelligent text splitting for optimal retrieval
4. **Embedding**: OpenAI embeddings for vector representation
5. **Storage**: Indexed in Weaviate for fast similarity search

### Conversation Flow

1. **User Input**: Received via REST API or WebSocket
2. **Context Retrieval**: Relevant documents fetched from vector DB
3. **LLM Processing**: Enhanced prompt with context sent to chosen LLM
4. **Response Generation**: Natural language response generated
5. **Memory Update**: Conversation history updated in database

## 🚀 Deployment

### Docker Deployment

```bash
docker build -t chatbot-saas .
docker run -p 8000:8000 chatbot-saas
```

### Heroku Deployment

```bash
git add .
git commit -m "Deploy to Heroku"
heroku create your-app-name
git push heroku main
```

### Railway Deployment

```bash
railway login
railway init
railway up
```

### AWS Elastic Beanstalk

```bash
eb init
eb create production
eb deploy
```

## 🧪 Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=app --cov-report=html
```

## 📊 Monitoring & Logging

- **Health Checks**: `/health` endpoint for service monitoring
- **Metrics**: Built-in request metrics and performance tracking
- **Logging**: Structured logging with configurable levels
- **Error Tracking**: Comprehensive error handling and reporting

## 🔒 Security Features

- JWT-based authentication
- Password hashing with bcrypt
- API rate limiting
- Input validation and sanitization
- CORS configuration
- Environment-based secrets management

## 🎨 Frontend (Optional)

A React-based chat interface is included in the `frontend/` directory:

- Modern chat UI with real-time updates
- File upload interface
- Conversation management
- User authentication flows
- Responsive design

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- Documentation: [Wiki](https://github.com/yourusername/chatbot-saas/wiki)
- Issues: [GitHub Issues](https://github.com/yourusername/chatbot-saas/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/chatbot-saas/discussions)

## 🗺️ Roadmap

- [ ] Multi-tenant support
- [ ] Advanced analytics dashboard
- [ ] Plugin system for custom tools
- [ ] Voice chat capabilities
- [ ] Mobile app integration
- [ ] Enterprise SSO support

---

Built with ❤️ using FastAPI, LangChain, and modern AI technologies.