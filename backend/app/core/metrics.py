from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
CHAT_REQUESTS_TOTAL = Counter("chat_requests_total", "Total chat requests", ["mode"])
SEARCH_REQUESTS_TOTAL = Counter("search_requests_total", "Total search requests")
DOCUMENT_UPLOADS_TOTAL = Counter("document_uploads_total", "Total document uploads")
INDEX_JOBS_TOTAL = Counter("index_jobs_total", "Total index jobs", ["job_type"])
INDEX_JOB_FAILURES_TOTAL = Counter("index_job_failures_total", "Total failed index job items")
ACTIVE_INDEX_JOBS = Gauge("active_index_jobs", "Active index jobs")
FAILED_INDEX_JOBS_TOTAL = Gauge("failed_index_jobs_total", "Failed or partially failed index jobs")
