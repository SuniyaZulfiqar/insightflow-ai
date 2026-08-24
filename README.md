# InsightFlow AI

> **AI-Powered Business Intelligence & Data Analytics Platform**

InsightFlow AI is a full-stack business intelligence application that
lets users securely upload business datasets, inspect data quality,
clean and prepare data, build interactive dashboards, explore analytics,
generate AI-assisted insights, and export professional reports.

It was built as a portfolio-grade SaaS-style application with a React
frontend, FastAPI backend, PostgreSQL persistence, JWT-based
authentication, and a responsive analytics interface.

------------------------------------------------------------------------

## ✨ Key Features

### 🔐 Authentication & User Access

-   User registration and login
-   JWT-based authentication
-   Protected application access
-   Email-based verification/authentication flow
-   Secure session handling
-   User/workspace-aware dataset access

### 📂 Dataset Management

-   Upload business datasets in **CSV** and **XLSX** formats
-   Dataset selection and workspace management
-   Automatic column/type detection
-   Dataset metadata such as row and column counts
-   Data preview tables
-   Refresh and dataset switching

### 🧹 Data Quality & Cleaning

-   Missing-value detection
-   Duplicate-row detection
-   Data-quality review before modifications
-   User-controlled cleaning operations
-   Missing-value replacement for appropriate numeric/categorical data
-   Duplicate removal
-   Preview/approval workflow before applying amendments
-   Cleaned dataset persistence

### 📊 Interactive Analytics

-   Automatically generated visualizations from selected columns
-   Numeric summaries
-   Categorical distributions
-   Date-based analysis
-   Interactive charts
-   Dynamic chart tooltips with category/label context
-   Dashboard column selection
-   Responsive chart layouts

### 💡 AI Insights

-   Data-quality observations
-   Business-oriented insights and recommendations
-   Insight cards based on the current dataset and analysis results
-   Graceful handling of unavailable analysis

### 📄 Reporting & Exports

-   Professional PDF reports
-   Dashboard PDF export
-   Cleaned dataset PDF export
-   Cleaned CSV export
-   Dataset previews and analytical summaries
-   File downloads with appropriate file formats

### 📱 Responsive SaaS UI

-   Desktop, laptop, tablet, and mobile layouts
-   Responsive sidebar/navigation behavior
-   Responsive dashboards and cards
-   Mobile-friendly data tables
-   Responsive charts and controls
-   Consistent dark analytics theme

------------------------------------------------------------------------

## 🖥️ Screenshots

### Dashboard

![InsightFlow Dashboard](docs/screenshots/dashboard.png)

### Dataset Management

![InsightFlow Dataset Management](docs/screenshots/datasets.png)

### Analytics

![InsightFlow Analytics](docs/screenshots/analytics.png)

### Dashboard Builder

![InsightFlow Dashboard Builder](docs/screenshots/dashboard-builder.png)

------------------------------------------------------------------------

## 🏗️ Architecture

``` text
┌──────────────────────────────┐
│        React + Vite          │
│                              │
│ Dashboard                    │
│ Datasets                     │
│ Analytics                    │
│ AI Insights                  │
│ Reports                      │
│ Settings                     │
└──────────────┬───────────────┘
               │ HTTP / JSON / Multipart
               │ JWT Authorization
               ▼
┌──────────────────────────────┐
│          FastAPI             │
│                              │
│ Authentication               │
│ Dataset APIs                 │
│ Workspace APIs               │
│ Analytics                    │
│ Data Quality                 │
│ Cleaning                     │
│ Report Generation            │
└──────────────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌──────────────┐
│ PostgreSQL  │  │ Pandas /     │
│             │  │ ReportLab    │
│ Users       │  │              │
│ Workspaces  │  │ Data analysis│
│ Datasets    │  │ PDF exports  │
└─────────────┘  └──────────────┘
```

------------------------------------------------------------------------

## 🧰 Technology Stack

### Frontend

-   React
-   Vite
-   Recharts
-   Lucide React
-   Custom responsive CSS

### Backend

-   Python
-   FastAPI
-   Pydantic
-   SQLAlchemy
-   Uvicorn
-   Pandas
-   ReportLab
-   OpenPyXL

### Database

-   PostgreSQL
-   Alembic migrations

### Authentication

-   JWT access tokens
-   Password hashing
-   Email verification/authentication support

### Development & Deployment

-   Git / GitHub
-   Environment variables for configuration
-   Frontend and backend separated into independent applications

------------------------------------------------------------------------

## 📁 Project Structure

``` text
insightflow-ai/
│
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── auth/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── uploads/
│   ├── requirements.txt
│   ├── alembic.ini
│   └── .env.example
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
│
├── docs/
│   └── screenshots/
│
├── .gitignore
└── README.md
```

------------------------------------------------------------------------

## 🚀 Local Installation

### 1. Clone the repository

``` bash
git clone https://github.com/SuniyaZulfiqar/insightflow-ai.git
cd insightflow-ai
```

### 2. Backend setup

``` bash
cd backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Configure the backend environment variables using:

``` text
backend/.env.example
```

Do not commit the real `.env` file.

Run the database migrations:

``` bash
alembic upgrade head
```

Start FastAPI:

``` bash
uvicorn app.main:app --reload --port 8000
```

The backend will be available at:

``` text
http://127.0.0.1:8000
```

FastAPI's interactive API documentation is available at:

``` text
http://127.0.0.1:8000/docs
```

### 3. Frontend setup

Open a second terminal:

``` bash
cd frontend
npm install
npm run dev
```

Vite will normally start the frontend at:

``` text
http://localhost:5173
```

------------------------------------------------------------------------

## 🔑 Environment Variables

The application is designed to keep environment-specific values and
secrets outside the source code.

Typical configuration includes:

``` env
DATABASE_URL=
SECRET_KEY=
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=
FRONTEND_URL=
```

The exact variables should match the current `backend/.env.example` and
frontend configuration in the repository.

### Security

Never commit:

-   `.env`
-   Database passwords
-   JWT secrets
-   SMTP credentials
-   API keys
-   `node_modules`
-   Python virtual environments
-   `__pycache__`

------------------------------------------------------------------------

## 🔄 Typical User Workflow

``` text
Register
   ↓
Verify account / authenticate
   ↓
Login
   ↓
Upload CSV/XLSX dataset
   ↓
Inspect dataset
   ↓
Review data quality
   ↓
Preview cleaning changes
   ↓
Approve cleaning operations
   ↓
Build dashboard
   ↓
Explore Analytics
   ↓
Review AI Insights
   ↓
Generate Reports
   ↓
Export CSV / PDF
```

------------------------------------------------------------------------

## 📊 Dashboard Workflow

Users can select a dataset and choose the columns they want to
visualize.

InsightFlow analyzes the selected fields and generates appropriate
visualizations rather than forcing a fixed dashboard onto every dataset.

The dashboard supports: - Numeric fields - Categorical fields - Date
fields - Data-quality indicators - Interactive charts - Dataset
switching - Refreshing analysis - Responsive layouts

------------------------------------------------------------------------

## 🧹 Data Cleaning Workflow

InsightFlow uses a user-confirmed cleaning workflow.

The application first identifies data-quality problems and lets the user
review proposed amendments.

Supported operations include:

1.  Fill replaceable missing values
2.  Remove exact duplicate rows
3.  Preview the expected changes
4.  Approve the selected changes
5.  Persist the cleaned dataset
6.  Re-run analysis on the cleaned data
7.  Export the cleaned dataset

The goal is to avoid silently changing the user's source data.

------------------------------------------------------------------------

## 📄 Reporting

InsightFlow can generate report documents containing dataset
information, analytical summaries, quality findings, selected dashboard
information, and data previews.

PDF generation is handled on the backend using ReportLab so that the
generated document is a real PDF rather than a renamed JSON response.

Cleaned dataset PDF generation is also supported for sharing or offline
review.

------------------------------------------------------------------------

## 🔌 API Design

The backend is organized around FastAPI routers and services.

Major API areas include:

``` text
/auth
/datasets
/workspaces
/users
```

Dataset operations include functionality for: - Uploading datasets -
Listing datasets - Dataset previews - Analytics - Data-quality
analysis - Chart generation - Cleaning - PDF/report generation - Export
operations

FastAPI automatically exposes interactive documentation through `/docs`
during local development.

------------------------------------------------------------------------

## 🗄️ Database

PostgreSQL stores the application's persistent business data.

Core entities include:

-   Users
-   Workspaces
-   Datasets

Alembic is used to manage database schema migrations.

This allows the database schema to evolve without manually recreating
the database for every change.

------------------------------------------------------------------------

## 🧠 AI / Insight Layer

InsightFlow is designed as an AI-powered business intelligence
application.

The insight layer works alongside the analytical/data-quality layer so
that recommendations are grounded in the current dataset rather than
being detached from the actual data.

The project architecture was intentionally designed to be
deployment-friendly and compatible with API-based AI services rather
than depending on a local-only model runtime.

------------------------------------------------------------------------

## ☁️ Deployment

The project is structured as a separate frontend and backend
application, making it suitable for cloud deployment.

A typical production architecture is:

``` text
React / Vite
     │
     ▼
Frontend Hosting
     │
     │ HTTPS API requests
     ▼
FastAPI Backend
     │
     ├──────────────► PostgreSQL
     │
     └──────────────► Email / AI / external services
```

Recommended production practices:

-   Store secrets in hosting-provider environment variables.
-   Configure production CORS explicitly.
-   Use a managed PostgreSQL database.
-   Use HTTPS in production.
-   Never expose SMTP passwords, JWT secrets, database credentials, or
    AI API keys in frontend code.
-   Configure the frontend API URL through environment variables rather
    than hard-coding a local address.

------------------------------------------------------------------------

## 🧪 Testing Checklist

Before sharing a production deployment, verify:

-   [ ] User registration works
-   [ ] Email verification/authentication works
-   [ ] Login works
-   [ ] Protected pages require authentication
-   [ ] CSV upload works
-   [ ] XLSX upload works
-   [ ] Dataset preview loads
-   [ ] Data-quality analysis loads
-   [ ] Cleaning preview works
-   [ ] Cleaning approval works
-   [ ] Dashboard generation works
-   [ ] Analytics charts load
-   [ ] Chart tooltips show category + value
-   [ ] AI Insights loads
-   [ ] PDF report downloads correctly
-   [ ] Cleaned CSV downloads correctly
-   [ ] Cleaned PDF downloads correctly
-   [ ] Logout works
-   [ ] Mobile/tablet layouts remain usable
-   [ ] Production CORS is configured correctly

------------------------------------------------------------------------

## 🎯 Project Goals

InsightFlow AI was built to demonstrate practical full-stack skills
across:

-   Business Intelligence
-   Data Analytics
-   Data Cleaning
-   Interactive Visualization
-   AI-assisted Insights
-   REST APIs
-   Authentication
-   PostgreSQL
-   React
-   FastAPI
-   File Processing
-   PDF/CSV Export
-   Responsive SaaS UI
-   Cloud Deployment

------------------------------------------------------------------------

## 🔮 Future Improvements

Potential future extensions include:

-   More advanced predictive models
-   Natural-language analytics/Copilot
-   Scheduled reports
-   Automated email reports
-   Multi-user collaboration
-   Role-based permissions
-   Additional database connectors
-   More advanced AI recommendations
-   Saved dashboard configurations
-   Production monitoring and observability

------------------------------------------------------------------------

## 👩‍💻 Author

**Suniya Zulfiqar Ali**

Business Administration student focused on Marketing, Data Analytics,
AI, and technology-driven business solutions.

**GitHub:** [SuniyaZulfiqar](https://github.com/SuniyaZulfiqar)

------------------------------------------------------------------------

## 📌 Project Status

**InsightFlow AI --- Final portfolio/deployment version**

The repository represents the final working application version prepared
for deployment and testing.
