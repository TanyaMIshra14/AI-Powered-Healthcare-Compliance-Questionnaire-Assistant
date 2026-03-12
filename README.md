# AI-Powered-Healthcare-Compliance-Questionnaire-Assistant

Overview

The AI-Powered Healthcare Compliance Questionnaire Assistant is a Python-based application designed to automate responses to healthcare compliance questionnaires. It uses Retrieval-Augmented Generation (RAG) to retrieve relevant information from policy documents and generate structured answers.
The system provides a web interface built with FastAPI and Jinja2 templates, allowing users to upload questionnaires, retrieve compliance information, and export responses.
This tool helps reduce the manual effort required to answer security, infrastructure, and compliance-related healthcare questionnaires.

Key Features

Automated Questionnaire Processing – Upload compliance questionnaires and generate responses automatically.
Retrieval-Augmented Generation (RAG) – Retrieves relevant information from reference policy documents before generating answers.
Secure User Authentication – Password hashing using bcrypt for secure login.
Document Management – Upload reference compliance documents for knowledge retrieval.
Response Exporting – Export generated responses for further use.
Web Interface – Interactive dashboard built with FastAPI and HTML templates.

Tech Stack

Python
FastAPI
SQLite
bcrypt (Password Hashing)
Jinja2 Templates
Retrieval-Augmented Generation (RAG)

Project Architecture

The system works in the following steps:

User Authentication
Users log in securely using hashed passwords.

Questionnaire Upload
Users upload healthcare compliance questionnaires.

Document Retrieval
The system searches reference documents for relevant policy information.

Answer Generation
The RAG pipeline generates structured answers using retrieved knowledge.

Export Results
Generated responses can be exported for submission or review.

Project Structure

almabase_healthcare_tool/
│
└── fixed_tool/
    ├── main.py                # FastAPI application entry point
    ├── auth.py                # Authentication and password hashing
    ├── database.py            # Database connection setup
    ├── models.py              # Database models
    ├── rag.py                 # Retrieval-Augmented Generation pipeline
    ├── export.py              # Export generated responses
    ├── requirements.txt       # Project dependencies
    ├── healthcare.db          # SQLite database
│
├── templates/
│   ├── home.html
│   ├── login.html
│   ├── dashboard.html
│   └── results.html

Installation
1. Clone the Repository
git clone https://github.com/yourusername/almabase_healthcare_tool.git
cd almabase_healthcare_tool

2. Create a Virtual Environment
python -m venv venv
source venv/bin/activate     # Mac/Linux
venv\Scripts\activate        # Windows

3. Install Dependencies
pip install -r requirements.txt

4. Run the Application
uvicorn main:app --reload

5. Open in Browser
http://127.0.0.1:8000

Example Workflow
Login to the system.
Upload a healthcare compliance questionnaire.
The system retrieves relevant information from policy documents.
AI generates structured answers.
Export responses for submission.

Future Improvements
Integration with vector databases (FAISS / ChromaDB) for better retrieval.
Support for PDF and DOCX questionnaire uploads.
Integration with LLMs for improved answer generation.
Advanced semantic search for compliance policies.
