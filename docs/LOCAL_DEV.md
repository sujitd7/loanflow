# Running LoanFlow locally

Two ways: with Docker (matches production) or natively (works today even without
virtualization). Both use the same code.

---

## Option A — Docker (preferred, needs setup on this machine)

Docker Desktop currently fails here: **Intel VT-x is disabled in BIOS** and **WSL2
is not installed**. Fix both, then `docker compose up` works.

### 1. Enable virtualization in BIOS/UEFI
1. Reboot and enter firmware setup (tap `F2`, `Del`, or `F10` at the vendor logo —
   varies by laptop; for many it's `F2`).
2. Find **Intel Virtualization Technology** / **Intel VT-x** (usually under
   *Advanced → CPU Configuration* or *Security*). Set it to **Enabled**.
3. Save and exit. Back in Windows, confirm:
   ```powershell
   (Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled   # should be True
   ```

### 2. Install WSL2 (Docker Desktop's backend on Windows 11 Home)
In an **Administrator** PowerShell:
```powershell
wsl --install
```
Reboot when it asks.

### 3. Start Docker Desktop
Settings → General → "Use the WSL 2 based engine" should be ticked. Then:
```bash
cp .env.example .env
docker compose up --build
```
web → http://localhost:5173 · api → http://localhost:8000/docs

---

## Option B — Native, no Docker (unblocked right now)

You need a Postgres to point at. Fastest is a free cloud one:

1. Create a free database at **https://neon.tech** (or Supabase / Railway).
2. Copy its connection string. Neon gives you
   `postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require` — rewrite the
   scheme to `postgresql+psycopg://` and keep the rest:
   ```
   DATABASE_URL=postgresql+psycopg://user:pass@ep-xxx.neon.tech/dbname?sslmode=require
   ```
3. Put that line in a `.env` file at the repo root (copy from `.env.example` and
   edit `DATABASE_URL`).

### API
```bash
cd api
python -m venv .venv
.venv\Scripts\activate           # PowerShell:  .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

### Worker (separate terminal)
```bash
cd worker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m worker.main
```

### Web (separate terminal)
```bash
cd web
npm install
npm run dev                      # http://localhost:5173
```
The Vite dev server proxies `/api` to `http://localhost:8000` by default, so the
frontend reaches the API with no extra config.

### Tests without a database
`pytest` falls back to in-memory SQLite automatically — no `DATABASE_URL` needed:
```bash
cd api && pytest -q
```

---

## Notes

- CI (GitHub Actions) runs its own Postgres service container, so pushing and PR
  checks work regardless of local Docker.
- Deployment (P8) needs Docker images built — that happens in CI, not on this
  machine, so a broken local Docker doesn't block deploy either.
- Once BIOS virtualization is on, Option A is the better daily driver because it
  matches production exactly (same Postgres version, same networking).
