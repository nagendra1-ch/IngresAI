# INGRES AI: India's Ground Water Resource Estimation System Assistant

INGRES AI is a modern, responsive full-stack web application that serves as an AI-powered groundwater intelligence and virtual assistant platform for India. It allows government officials, researchers, and analysts to search district groundwater levels, compare districts, visualize statistics through interactive charts, and consult a natural language virtual assistant that interprets database statistics using the Gemini API.

---

## 🏗️ Architecture

```
React Frontend (Vite)
       │
       │ REST API (JWT Authenticated)
       ▼
FastAPI Backend
       │
       ├── Authentication & User Management (Role-based: USER, ADMIN)
       ├── Groundwater Data & Search Services
       ├── District Comparison & AI Synthesis Engine
       ├── Dashboard Stats Aggregations
       ├── Query History Tracker & Result Access Counters
       ├── Excel Exporter (Pandas + OpenPyXL)
       └── Gemini AI Service (System Prompts + Local DB Verification)
       │
       ├─► Gemini API
       │
       └─► Database (PostgreSQL / SQLite)
```

**Data Integrity Rule**: Numerical information is retrieved directly from the verified database. The Gemini AI service acts solely as a natural language compiler to construct friendly summaries, completely preventing the fabrication or hallucination of groundwater numbers.

---

## 🛠️ Technology Stack

### Frontend
- **Framework**: React (Vite) + JavaScript
- **Routing**: React Router DOM (v6)
- **HTTP Client**: Axios (configured with auto-JWT interceptors)
- **Visualization**: Recharts (fully responsive charts)
- **Styling**: Plain CSS (Custom CSS Variables, modern cards, and responsive sidebar layouts)

### Backend & Database
- **Framework**: FastAPI (Python)
- **ORM**: SQLAlchemy
- **Data Processing**: Pandas & OpenPyXL
- **AI Core**: Google Generative AI (`google-generativeai`)
- **Database**: SQLite (Default for quick dev) / PostgreSQL (Fully compatible)
- **Security**: JWT tokens + password hashing with Passlib (Bcrypt)

---

## ⚙️ Environment Variables

A `.env` file must exist in the `backend/` directory.

### Example `backend/.env`
```env
DATABASE_URL=sqlite:///./ingres_ai.db
GEMINI_API_KEY=your_gemini_api_key_here
JWT_SECRET_KEY=your_secure_secret_key_here
JWT_ALGORITHM=HS256
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## 🚀 Installation & Local Startup

### 1. Backend Setup
1. Open a terminal and navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` variables (e.g., set `GEMINI_API_KEY`).
5. Initialize the database schema and seed the initial district dataset:
   ```bash
   python scripts/import_data.py
   ```
6. Start the FastAPI application server:
   ```bash
   python -m uvicorn app.main:app --port 8085
   ```

The backend documentation will be accessible at: `http://127.0.0.1:8085/docs`

### 2. Frontend Setup
1. Open a new terminal and navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install Node packages:
   ```bash
   npm install
   ```
3. Start the Vite React development server:
   ```bash
   npm run dev
   ```

The web application will open at: `http://localhost:5173`

---

## 🔒 Pre-Seeded Accounts

Running `scripts/import_data.py` seeds two default accounts representing both role-based access permissions:

1. **Standard User**:
   - **Email**: `user@ingres.gov.in`
   - **Password**: `userpassword`
   - **Capabilities**: Ask questions, compare districts, search data, inspect dashboards, view personal history.
   
2. **Administrator**:
   - **Email**: `admin@ingres.gov.in`
   - **Password**: `adminpassword`
   - **Capabilities**: Standard user features + view total users, list queries, inspect district view logs, and download multi-sheet Excel reports.

---

## 🗃️ Seeding Custom Datasets

Administrators can seed custom datasets using a CSV file matching this header structure:
`State,District,Groundwater Level,Rainfall,Recharge,Extraction,Availability,Assessment Category,Year`

To run the import utility, place your dataset at `backend/data/groundwater_seed.csv` and run:
```bash
python scripts/import_data.py
```
The script will perform strict type validation, skip incomplete rows, and check for duplicates (updating existing entries for the same year instead of duplicating).

---

## 🔌 API Documentation Summary

### Authentication
- `POST /api/auth/register` - Sign up standard user
- `POST /api/auth/login` - Secure JWT login session
- `GET /api/auth/me` - Profile details (Protected)
- `POST /api/auth/logout` - Clear cookies/history

### AI Virtual Assistant
- `POST /api/ai/chat` - Chat bot question processing (Protected)
- `GET /api/ai/history` - User specific chat logs (Protected)
- `GET /api/ai/history/{id}` - Retrieve detailed query/response exchange (Protected)

### District Metrics
- `GET /api/districts` - Dropdown selector list (Protected)
- `GET /api/districts/search` - Search by name/state (Protected)
- `GET /api/districts/{id}` - Historical survey metrics & logs view event (Protected)
- `GET /api/districts/{id}/statistics` - Chronological line-chart values (Protected)
- `GET /api/compare` - Compares two districts & triggers AI analysis (Protected)

### Groundwater Dashboards
- `GET /api/dashboard/summary` - Mapped counts, top/bottom performing district rankings
- `GET /api/dashboard/state-statistics` - State-wide averages
- `GET /api/dashboard/district-statistics` - Global stats list
- `GET /api/dashboard/rainfall` - Rainfall bar chart parameters
- `GET /api/dashboard/groundwater` - Pie chart category counts

### Administration
- `GET /api/admin/statistics` - Summary metrics card values (Admin only)
- `GET /api/admin/users` - Registered accounts list + metrics (Admin only)
- `GET /api/admin/queries` - Global question log history (Admin only)
- `GET /api/admin/access-statistics` - District visitor counter lists (Admin only)
- `GET /api/admin/export-excel` - Download multi-sheet openpyxl Excel spreadsheet (Admin only)
