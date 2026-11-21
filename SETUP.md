# Vivakriss gallery integration — local test

1. Back up your existing project and database. Copy `backend/main.py` and `backend/seed_products.py` into your existing `vivakriss_prduction_starter/backend` folder. Copy `index.html` into `vivakriss_prduction_starter` (keep the existing `assets/` folder).
2. In Anaconda Prompt: `cd C:\Users\ojoam\vivakriss_prduction_starter\backend` (adjust if your folder differs).
3. Activate: `.venv\Scripts\activate` and start with `python -m uvicorn main:app --host 127.0.0.1 --port 8010`.
4. In a SECOND Anaconda Prompt, activate the same environment and run `python seed_products.py` once. It does not overwrite existing product values.
5. Open the website with a local HTTP server, e.g. from project root: `python -m http.server 5500`, then browse `http://127.0.0.1:5500`. In Manage Products, enter `http://127.0.0.1:8010`, then log in using the admin account you created. **Do not publish credentials.**
6. Important: backend CORS `ALLOWED_ORIGINS` must include `http://127.0.0.1:5500` for local testing. Set it before starting the backend (Windows cmd: `set ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500`). For production, use your actual HTTPS GitHub Pages origin and HTTPS backend URL.

## Boundaries
- The existing Admin Demo remains a browser-only preview; use **Manage Products** for persistent edits.
- The storefront attempts to fetch the live catalogue but falls back to its demo data when offline. **Do not use this fallback as proof of live pricing or stock.**
- The existing checkout is still a demonstration. No public order creation or automatic payment verification was added. Do not collect funds based on the preview.
- For production, replace the default localhost API URL with the real HTTPS Render URL in the page configuration, use HTTPS and set CORS correctly. Never publish `JWT_SECRET`, admin passwords or `.env` files. Database migrations, backups, authenticated image uploads, and full end-to-end tests remain required.
