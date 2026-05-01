from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright, Browser
from contextlib import asynccontextmanager
from typing import Optional


# -----------------------------
# BROWSER STATE
# -----------------------------

state: dict = {}


# -----------------------------
# CUSTOM ERROR CLASS
# -----------------------------

class ScraperError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code


# -----------------------------
# LIFESPAN - BROWSER STAYS ALIVE
# -----------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    playwright = await async_playwright().start()
    state["browser"] = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    state["playwright"] = playwright
    print("✅ Browser started")

    yield

    await state["browser"].close()
    await state["playwright"].stop()
    print("🛑 Browser closed")


# -----------------------------
# APP
# -----------------------------

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock to your frontend URL in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# ERROR HANDLER
# -----------------------------

@app.exception_handler(ScraperError)
async def scraper_error_handler(request: Request, exc: ScraperError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        }
    )


# -----------------------------
# REQUEST / RESPONSE MODELS
# -----------------------------

class ScrapeRequest(BaseModel):
    url: str

class ScrapeResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None


# -----------------------------
# SCRAPER LOGIC
# -----------------------------

async def scrape_job(url: str) -> dict:
    browser: Browser = state["browser"]

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Block images, css, fonts for speed
    await context.route(
        "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}",
        lambda route: route.abort()
    )

    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector("h1", timeout=10000)

        # Dismiss modal
        try:
            dismiss_btn = page.locator('[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]')
            await dismiss_btn.wait_for(state="visible", timeout=5000)
            await dismiss_btn.click()
            await page.wait_for_selector(".show-more-less-html__markup", timeout=5000)
        except:
            pass

        # Scroll to trigger lazy loads
        await page.mouse.wheel(0, 2000)

        # Expand description
        try:
            show_more = page.locator('[data-tracking-control-name="public_jobs_show-more-html-btn"]')
            await show_more.wait_for(state="visible", timeout=3000)
            await show_more.click()
            await page.wait_for_selector(".show-more-less-html__markup", timeout=5000)
        except:
            pass

        # Title
        title = "N/A"
        try:
            title = (await page.locator("h1.topcard__title").text_content()).strip()
        except:
            try:
                title = (await page.locator("h1").first.text_content()).strip()
            except:
                pass

        # Company
        company = "N/A"
        try:
            company = (await page.locator(".topcard__org-name-link").text_content()).strip()
        except:
            try:
                company = (await page.locator('[data-tracking-control-name="public_jobs_topcard-org-name"]').text_content()).strip()
            except:
                pass

        # Location
        location = "N/A"
        try:
            location = (await page.locator(".topcard__flavor--bullet").first.text_content()).strip()
        except:
            pass

        # Company logo
        logo_url = "N/A"
        try:
            logo = page.locator(".top-card-layout__card .artdeco-entity-image").first
            logo_url = await logo.get_attribute("src") or await logo.get_attribute("data-delayed-url") or "N/A"
        except:
            pass

        # Description
        description = "N/A"
        try:
            description = (await page.locator(".show-more-less-html__markup").text_content()).strip()
        except:
            pass

        # Criteria
        details = {}
        try:
            items = page.locator(".description__job-criteria-item")
            count = await items.count()
            for i in range(count):
                try:
                    label = (await items.nth(i).locator("h3").text_content()).strip()
                    value = (await items.nth(i).locator("span").text_content()).strip()
                    details[label] = value
                except:
                    continue
        except:
            pass

        return {
            "title": title,
            "company": company,
            "location": location,
            "logo_url": logo_url,
            "description": description,
            "details": {
                "seniority_level": details.get("Seniority level", "N/A"),
                "employment_type": details.get("Employment type", "N/A"),
                "job_function": details.get("Job function", "N/A"),
                "industries": details.get("Industries", "N/A"),
            },
            "source_url": url,
        }

    finally:
        await context.close()


# -----------------------------
# ROUTES
# -----------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "browser_active": state.get("browser") is not None
    }


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest):

    if not request.url:
        raise ScraperError("MISSING_URL", "No URL provided", 400)

    if "linkedin.com/jobs" not in request.url:
        raise ScraperError("INVALID_URL", "Only LinkedIn job URLs are supported", 400)

    if state.get("browser") is None:
        raise ScraperError("BROWSER_UNAVAILABLE", "Browser instance is not running", 503)

    try:
        data = await scrape_job(request.url)

        # If we got nothing useful, the job probably doesn't exist anymore
        if data["title"] == "N/A" and data["description"] == "N/A":
            raise ScraperError(
                "SCRAPE_FAILED",
                "Page loaded but no job data found — job may have been removed or URL is invalid",
                422
            )

        return ScrapeResponse(success=True, data=data)

    except ScraperError:
        raise  # let the error handler above deal with it

    except TimeoutError:
        raise ScraperError("TIMEOUT", "Page took too long to load", 504)

    except Exception as e:
        raise ScraperError("INTERNAL_ERROR", str(e), 500)