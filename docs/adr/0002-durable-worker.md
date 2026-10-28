---
status: accepted
---
# Keep one domain model with a durable media worker

Owner explicitly approved this local V02 stack on 2026-10-28: React/TypeScript, FastAPI/Python durable worker, PostgreSQL, private storage, FFmpeg and explicit Standard Meta adapter. Package/runtime pins remain routine engineering choices. Deployment, publication and new paid calls require separate authority. Acceptance of this architectural decision is distinct from independent implementation acceptance.

Use a React client and Python API/worker sharing PostgreSQL state, with private media storage and versioned Standard Meta adapter. A separate leased worker costs more setup than request-local tasks but permits restart recovery, deletion fencing and cost accounting; a PostgreSQL job table avoids adding a broker before workload evidence warrants one. Rejected alternatives are request-only serverless processing and a microservice per stage; paid deployment remains unapproved.
