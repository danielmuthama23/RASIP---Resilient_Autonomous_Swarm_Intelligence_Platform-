from __future__ import annotations
import asyncio, os, time
from dataclasses import dataclass
from pathlib    import Path
from typing     import Any, Dict, List, Optional

# Microsoft Fabric OneLake — Azure Data Lake Storage Gen2
ONELAKE_ACCOUNT  = os.getenv("ONELAKE_ACCOUNT",  "rasip")
ONELAKE_FS       = os.getenv("ONELAKE_FS",       "onelake")
WORKSPACE_ID     = os.getenv("FABRIC_WORKSPACE_ID", "")
LAKEHOUSE_ID     = os.getenv("FABRIC_LAKEHOUSE_ID",  "")
TABLE_PATH       = "Tables/swarm_telemetry"
FILES_PATH       = "Files/telemetry"
PARQUET_CHUNK    = 1000   # rows per parquet file

@dataclass
class WriteResult:
    success:     bool
    path:        str = ""
    rows:        int = 0
    write_time:  float = 0.0
    error:       str = ""

class OneLakeClient:
    """
    Microsoft Fabric OneLake client.
    Writes telemetry to:
      • Tables/ — Delta Lake table (queryable via KQL/SQL)
      • Files/  — raw Parquet for ML training pipelines
    Uses azure-storage-file-datalake (ADLS Gen2 SDK).
    """

    def __init__(self):
        self._client  = None   # lazy ADLS client init
        self._pending: List[Dict] = []
        self._written_rows = 0

    # ── Lazy client initialisation ────────────────────────
    def _get_client(self):
        if self._client is not None: return self._client
        try:
            from azure.storage.filedatalake import DataLakeServiceClient
            from azure.identity            import DefaultAzureCredential
            url = f"https://{ONELAKE_ACCOUNT}.dfs.fabric.microsoft.com"
            self._client = DataLakeServiceClient(
                account_url = url,
                credential  = DefaultAzureCredential(),
            )
        except ImportError:
            self._client = "mock"
        return self._client

    # ── Append events to Delta table ──────────────────────
    async def append(self, events: List[Any]) -> WriteResult:
        """Write a batch of TelemetryEvents to the Delta table."""
        self._pending.extend([
            e.__dict__ if hasattr(e, "__dict__") else e
            for e in events
        ])
        if len(self._pending) >= PARQUET_CHUNK:
            return await self._flush_delta()
        return WriteResult(success=True, rows=0)

    async def _flush_delta(self) -> WriteResult:
        rows = self._pending[:PARQUET_CHUNK]
        self._pending = self._pending[PARQUET_CHUNK:]
        t0 = time.monotonic()
        try:
            path = await self._write_parquet(rows, TABLE_PATH)
            self._written_rows += len(rows)
            return WriteResult(
                success    = True,
                path       = path,
                rows       = len(rows),
                write_time = time.monotonic() - t0,
            )
        except Exception as e:
            return WriteResult(success=False, error=str(e))

    # ── Write raw Parquet to Files/ ───────────────────────
    async def write_parquet(self, rows: List[Dict],
                           prefix: str = FILES_PATH) -> WriteResult:
        """Write rows directly to Files/ as a Parquet snapshot."""
        t0 = time.monotonic()
        try:
            path = await self._write_parquet(rows, prefix)
            return WriteResult(success=True, path=path,
                               rows=len(rows),
                               write_time=time.monotonic() - t0)
        except Exception as e:
            return WriteResult(success=False, error=str(e))

    async def _write_parquet(self, rows: List[Dict],
                            dest_prefix: str) -> str:
        fname = f"{dest_prefix}/part-{int(time.time()*1000)}.parquet"
        client = self._get_client()
        if client == "mock":
            await asyncio.sleep(0)
            return fname
        try:
            import pandas as pd
            import io
            buf = io.BytesIO()
            pd.DataFrame(rows).to_parquet(buf, index=False)
            buf.seek(0)
            fs_client = client.get_file_system_client(ONELAKE_FS)
            fc = fs_client.get_file_client(
                f"{WORKSPACE_ID}/{LAKEHOUSE_ID}/{fname}")
            fc.upload_data(buf.read(), overwrite=True)
        except ImportError:
            await asyncio.sleep(0)
        return fname

    # ── Data lifecycle ────────────────────────────────────
    async def list_files(self, prefix: str = FILES_PATH) -> List[str]:
        """List Parquet files stored under a path prefix."""
        client = self._get_client()
        if client == "mock": return []
        try:
            fs = client.get_file_system_client(ONELAKE_FS)
            return [
                p.name for p in fs.get_paths(path=prefix)
                if p.name.endswith(".parquet")
            ]
        except Exception:
            return []

    def stats(self) -> Dict:
        return {"written_rows": self._written_rows,
                "pending": len(self._pending)}
