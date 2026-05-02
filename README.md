# LinkedIn Job Scraper API

A lightweight REST API that scrapes LinkedIn job listings and returns structured data. Built with FastAPI and Playwright.

---

## Features

- Scrapes job title, company, location, logo, description, and criteria from any LinkedIn job URL
- Persistent Chromium browser instance — no cold start on every request
- Blocks images, CSS, and fonts for faster scraping
- Consistent JSON response structure with typed error codes
- Docker-ready for deployment

---

## Tech Stack

- **Python** — core language
- **FastAPI** — API framework
- **Playwright** — headless browser automation
- **Uvicorn** — ASGI server
- **Docker** — containerization

---

## Project Structure

```
.
├── scraper.py       # main application
├── requirements.txt # dependencies
├── Dockerfile       # container config
└── .gitignore
```

---

## Local Development

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
# Clone the repo
git clone https://github.com/ad-tobii/linkedin-job-url-scraper.git
cd linkedin-job-url-scraper

# Install dependencies
pip install -r requirements.txt

# Install Chromium
playwright install chromium

# Start the server
python -m uvicorn scraper:app --host 0.0.0.0 --port 8000
```

Server runs at `http://localhost:8000`

---

## API Reference

### Health Check

```
GET /health
```

**Response**
```json
{
  "status": "ok",
  "browser_active": true
}
```

---

### Scrape Job

```
POST /scrape
```

**Request Body**
```json
{
  "url": "https://www.linkedin.com/jobs/view/4406272813"
}
```

**Success Response**
```json
{
  "success": true,
  "data": {
    "title": "Frontend Developer | $70/hr Remote",
    "company": "Crossing Hurdles",
    "location": "Nigeria",
    "logo_url": "https://media.licdn.com/...",
    "description": "Position: Frontend Engineer...",
    "details": {
      "seniority_level": "Associate",
      "employment_type": "Contract",
      "job_function": "Engineering and Information Technology",
      "industries": "Software Development, IT Services and IT Consulting"
    },
    "source_url": "https://www.linkedin.com/jobs/view/4406272813"
  },
  "error": null
}
```

**Error Response**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_URL",
    "message": "Only LinkedIn job URLs are supported"
  }
}
```

---

### Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `MISSING_URL` | 400 | No URL provided in request body |
| `INVALID_URL` | 400 | URL is not a LinkedIn job URL |
| `BROWSER_UNAVAILABLE` | 503 | Browser instance is not running |
| `SCRAPE_FAILED` | 422 | Page loaded but no job data found — job may have been removed |
| `TIMEOUT` | 504 | Page took too long to load |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Deployment

### Docker

```bash
# Build image
docker build -t linkedin-scraper .

# Run container
docker run -p 8000:8000 linkedin-scraper
```

### Render

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set environment to **Docker**, port to **8000**
5. Deploy
6. Set Health Check Path to `/health` in service settings

> **Note:** Render free tier spins down after 15 minutes of inactivity. Set up a cron job (e.g. [cron-job.org](https://cron-job.org)) to ping `/health` every 14 minutes to keep the service alive.

---

## Usage Example

```javascript
// From your frontend or n8n workflow
const response = await fetch("https://your-service.onrender.com/scrape", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    url: "https://www.linkedin.com/jobs/view/4406272813"
  })
});

const data = await response.json();
console.log(data.data.title); // "Frontend Developer | $70/hr Remote"
```

---

## Limitations

- Only supports LinkedIn job URLs (`linkedin.com/jobs/...`)
- Single browser instance — not optimized for high concurrency
- Dependent on LinkedIn's public HTML structure — selectors may need updating if LinkedIn changes their DOM

---

## License

MIT
