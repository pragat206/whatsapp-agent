# kb_docs

Ingest-ready knowledge-base documents for the Terra Rex WhatsApp
chatbot. Each file is structured so the chunker
(`backend/app/services/kb/indexer.py`) and the retriever
(`backend/app/services/kb/retriever.py`) can match individual Q&A
items against incoming customer messages.

## Why these exist (not the original PDFs)

The original training PDFs (`TerraRex_WhatsApp_Chatbot_Training_HINDI`
and `TerraRex_WhatsApp_Chatbot_Hindi`) embed Devanagari and Latin glyphs
with font subsets that `pypdf` cannot map back to Unicode — half the
text extracts as blank characters or partial fragments. That makes them
useless as KB sources: the bot ends up retrieving empty chunks and
hallucinating prices.

These Markdown files carry the same content as clean UTF-8 so the
existing PDF / Markdown upload endpoint (`POST /api/v1/kb/{kb_id}
/documents/upload`) can ingest them losslessly.

## Files

- `terrarex_training_hindi.md` — full Hindi/Hinglish training script
  (welcome, system types, pricing, subsidy, financing, AMC, objection
  handling, booking flow).
- `terrarex_training_english.md` — English mirror of the same content
  for customers who write in English.
- `terrarex_faqs.md` — flat list of Q&A pairs in both languages,
  short-form, optimized for the FAQ matcher.
- `terrarex_quick_reference.md` — pricing tables, subsidy slabs,
  recommended system size by monthly bill — pure facts the model must
  ground on.

## How to ingest

1. Open the dashboard's Knowledge Base tab.
2. Pick the agent's KB (or create one and link it on the Agent tab).
3. Upload each `.md` file via the "Upload document" button. The
   indexer chunks them and generates embeddings automatically.

Re-upload whenever a price, subsidy figure, or partner bank list
changes.
