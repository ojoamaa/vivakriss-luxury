# Vivakriss Luxury — Production Backend Starter

## Current state
The existing GitHub Pages storefront is preserved **unchanged**. The new `backend/` folder is a first backend milestone, **not yet connected** to the storefront. Do not accept real payments/orders through the existing demo.

## Local setup (Windows PowerShell)
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:JWT_SECRET = 'replace-with-a-random-long-secret-of-at-least-32-characters'
python create_admin.py
uvicorn main:app --reload
```
Then visit http://127.0.0.1:8000/docs. Set DATABASE_URL to PostgreSQL to test production parity.

## API flow
1. Owner/admin logs in at `POST /admin/login` (bearer token).
2. Admin confirms product stock or bespoke quotation and creates a priced order at `POST /admin/orders`. **Customer-entered prices are not trusted.**
3. Customer transfers to Stanbic IBTC / Vivakriss Luxury / 0035278358 after confirmation.
4. Customer submits a JPEG/PNG/PDF receipt at `POST /orders/{id}/receipt` using multipart fields `amount`, `transfer_reference`, `file`. This is only evidence, **not** bank verification.
5. Admin views private receipt via `GET /admin/payments/{id}/receipt`, checks actual bank credit independently, then approves/rejects via `POST /admin/payments/{id}/review` with `{"approve":true}`.
6. Bespoke production can begin after 70% verified; dispatch requires 100%. Ready-made dispatch requires 100%.

## Deploy
Use a Render PostgreSQL database with SSL and persistent backups, and a Render Python web service. Set `DATABASE_URL`, `JWT_SECRET`, `ENVIRONMENT=production`, `ALLOWED_ORIGINS=https://ojoamaa.github.io`. The `render.yaml` is a starting configuration; verify plan costs, database backups, HTTPS and operational availability. Never put secrets in GitHub.

## Before live launch (mandatory)
- Integrate frontend forms with API, replace public Admin Demo with authenticated admin interface.
- Implement customer order access tokens or verified email links, not only UUID identifiers; add rate limiting and bot protection.
- Implement transactional email and confirmation/quotation workflow, admin audit logging, and stock reservation with concurrency control.
- Add migrations (Alembic), automated tests, monitoring, database backups, data retention/privacy notices and operational recovery.
- Move receipt bytes from database to encrypted private object storage with malware scanning, signed access, retention policy, and access logs.
- Configure business approval for direct bank transfers and reconcile bank statements manually. Never rely on uploaded screenshot alone.
- Validate owner-approved bank details before enabling live checkout.

## Security notes
The prototype uses bearer tokens, a hashed admin password, server-side status controls and private receipt access. It is a development starter, not a security-audited live payments system. `POST /orders` intentionally refuses customer-provided price submissions until server-verified catalog/quotation flow is built.
