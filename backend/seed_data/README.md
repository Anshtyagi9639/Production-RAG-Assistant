# MongoDB seed data (development only)

Synthetic data for the MongoDB Atlas database `copilot`. Everything here is **development/demo
content**: two `@copilot.example.com` accounts, a demo workspace and a "Customs Wise" demo document.
It is not official customs guidance and not client information.

The files contain no passwords, password hashes, connection strings or API keys.

## Files

Each file is a JSON array for one collection, in MongoDB Extended JSON (`{"$uuid": ...}` for ids,
`{"$date": ...}` for timestamps). IDs are deterministic, and every reference points at a record
in another file.

| File | Collection | Contents |
|---|---|---|
| `users.json` | `users` | `admin@copilot.example.com` (Demo Admin), `member@copilot.example.com` (Demo Member). No `password_hash`. |
| `workspaces.json` | `workspaces` | "Production RAG Demo", plus "Member Sandbox" (used to check workspace isolation) |
| `workspace_members.json` | `workspace_members` | Admin = owner and member = member of the demo; member = owner of the sandbox |
| `documents.json` | `documents` | `customs-wise-demo.txt` (demo) and `member-sandbox-notes.txt` (sandbox), status `COMPLETED` |
| `document_chunks.json` | `document_chunks` | The documents split by the app's real chunker (800 tokens, 120 overlap) |
| `conversations.json` | `conversations` | "Customs Demo Conversation" (admin, demo workspace) |
| `messages.json` | `messages` | One user question and one clearly labelled demo answer |
| `agent_runs.json` | `agent_runs` | One completed demo run, labelled as created by the seed script |
| `activity_logs.json` | `activity_logs` | `workspace.created`, `member.added`, `document.uploaded`, `conversation.created` |

The JSON is generated from `backend/scripts/seed_mongodb.py`. Don't edit it by hand: change the
script and run `--export-json`. A unit test fails if the files and the script drift apart.

## Option 1 (recommended): seed script

1. In the repository-root `.env`, set `MONGODB_URI` and `MONGODB_DATABASE=copilot`, plus two
   development passwords of at least 8 characters:
   ```
   SEED_ADMIN_PASSWORD=<choose one>
   SEED_MEMBER_PASSWORD=<choose one>
   ```
2. From the repository root:
   ```
   python backend/scripts/seed_mongodb.py
   ```
   The script:
   - pings Atlas;
   - creates the collections with validators and indexes (`app/db/mongo_schema.py`);
   - upserts every seed record and sets the two passwords as argon2 hashes, using the app's own
     hashing code;
   - writes the two `.txt` source files into local storage;
   - checks every record and workspace isolation;
   - prints a summary. It never prints connection strings or secrets.
3. Optional: to make the demo document searchable, also embed its chunks into Qdrant. This needs
   `OPENAI_API_KEY`, `QDRANT_URL` and `QDRANT_API_KEY`:
   ```
   python backend/scripts/seed_mongodb.py --index-vectors
   ```

Running the script again updates the same records in place. It creates no duplicates, and it only
rehashes a password when the one in `.env` has changed.

## Option 2: Atlas Data Explorer

1. In Atlas, open **Copilot-Cluster → Browse Collections → database `copilot`**. Don't use
   "Load sample data".
2. For each file, open (or create) the collection with the same name, then
   **Add Data → Import JSON or CSV file**, and select that collection's file.
   `users.json` goes into `users`, `workspaces.json` into `workspaces`, and so on.
3. Imported users have **no password**, so they can't sign in until you run the seed script once
   (step 1 above). It only sets the hashes and fills anything missing.

Collections created this way have no validators or indexes. Run the seed script, or start the
backend, which runs the same schema setup, to add them.

## Verify

Check in Atlas, under **Browse Collections**:
- `users` holds 2 seed users (no `password_hash` until the script has run);
- `workspace_members` holds 3 seed records;
- `document_chunks` filtered with `{ "workspace_id": <Member Sandbox _id> }` returns only the
  sandbox chunk.

The seed script's `verification: PASS` line runs the same checks automatically.

## Reset

```
python backend/scripts/seed_mongodb.py --reset
```

This deletes only the records this script creates, matched by their fixed IDs. Anything else in
`copilot`, such as accounts you registered through the app, is left alone.
