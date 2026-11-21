# Vivakriss Luxury — GitHub Pages client review V1.3

A static, responsive demonstration using 19 original product photographs. No backend, payment gateway, or authenticated admin is connected.

## Confirmed client policies
- Home-based craftsmanship; delivery only. No pickup or physical shop claims.
- Ready-made products: shopping cart is an **enquiry**, not a purchase or reservation.
- Delivery method and charges agreed directly with the client.
- Bespoke: quotation first; at least **70% verified advance** before production starts. Remaining balance tracked; no real payment verification on this demo.

## Publish
1. Extract ZIP and upload `index.html` and `assets/` into the root of a GitHub repository.
2. Settings → Pages → Deploy from a branch → `main` / `(root)`.
3. Confirm owner approval for public use of product photos and WhatsApp number before publishing.

## Demo limitations
Cart and bespoke requests exist only in browser localStorage. The WhatsApp cart button opens a prefilled message, which the user must send. Prices, availability, delivery fees, and payment instructions must be confirmed by Vivakriss. No card payments or automatic stock reservations.

The admin demonstration is intentionally **not** linked in public navigation and is **not secure**. A proper private admin dashboard requires FastAPI, PostgreSQL, authentication and verified payment records. Do not enter genuine customer or payment details into the static demo.

Developed as a client-review concept by DataDev Limited.


## v1.4.1 Admin Demo navigation fix
The homepage navigation now includes **Admin Demo**, opening the existing browser-only dashboard. The `#admin-preview` direct link remains functional. This is public demo functionality, not authentication or live order processing. Upload all root files and the entire `assets/` directory to the repository main branch (root) to deploy.


## v1.5 Bank transfer checkout preview
- Client-approved bank: Stanbic IBTC Bank / Vivakriss Luxury / 0035278358.
- New Checkout Demo tab; customer and delivery fields, ready-made 100% or bespoke 70% calculation, receipt filename selection, local test payment record, and admin payment demo table.
- **Not production payment processing:** no uploaded receipt bytes, backend, shared database, secure login, bank reconciliation, or real order submission. The browser-only demonstration must not be used to process customer orders.
- Production requires authenticated API, private object storage, server-side pricing and stock validation, admin RBAC, payment audit trail and verification, and dispatch gating after confirmed cleared funds.
