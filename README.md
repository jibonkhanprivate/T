# TopUpers Flask starter

This is a **functional Flask MVP inspired by the uploaded PHP project**, not a complete port of all 514 original archive entries. It provides responsive game browsing, searchable game cards, packages, registration/login, SQLite storage, pending order requests, and a signed-in order history.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Set `SECRET_KEY` to a stable secret in production. Use a proper WSGI server, HTTPS, CSRF protection as provided, rate limits, email verification, and stronger operational controls before deployment.

## Important limitations

- Sample catalog/prices are demonstration data, **not** imported live product records or verified prices.
- Checkout **only creates a pending request**; no money is collected, no payment method is enabled, and no game credits are delivered.
- Original PHP admin panel, supplier integrations, webhooks, wallet, vouchers, refunds, full content management, and other modules have not been migrated.
- For production, add payment verification, order fulfillment integration, admin roles, rate limiting, audit logs, backups, and robust validation.
