# user_uploads

Storage for documents and media that customers send into the WhatsApp
chatbot (electricity bills, Aadhaar copies, roof photos, voice notes,
PDFs of competitor quotations, etc.).

## Layout

Files land under per-contact subfolders:

```
user_uploads/
  <phone_e164>/
    <message_id>__<original_basename_or_type>.<ext>
```

For example, an inbound image from `+919900000000` on message
`a1b2c3...` is saved as:

```
user_uploads/+919900000000/a1b2c3...__image.jpg
```

## Configuration

The root path is controlled by the `USER_UPLOADS_DIR` environment
variable (see `backend/app/core/config.py`). Default: `user_uploads/`
at the repo root.

Saving happens best-effort inside the inbound webhook flow — a network
or disk failure here never blocks the AI reply or marks the message as
failed. See `backend/app/services/media/storage.py`.

## Privacy

These files contain customer PII (Aadhaar, bank passbook scans, bills).
The folder is `.gitignored` so they never enter version control. In
production, mount this path to durable storage and apply the same
access controls as your database.
