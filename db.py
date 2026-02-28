import aiosqlite
from typing import Any, Dict, List, Optional
import json
from datetime import datetime

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL CHECK(role IN ('client','company'))
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            contact TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_tg_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            price TEXT NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(request_id, company_id)
        )
        """)
        await db.commit()


async def set_user_role(tg_id: int, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users(tg_id, role) VALUES(?, ?) "
            "ON CONFLICT(tg_id) DO UPDATE SET role=excluded.role",
            (tg_id, role),
        )
        await db.commit()


async def get_user_role(tg_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role FROM users WHERE tg_id=?", (tg_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def upsert_company(tg_id: int, name: str, contact: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO companies(tg_id, name, contact) VALUES(?, ?, ?) "
            "ON CONFLICT(tg_id) DO UPDATE SET name=excluded.name, contact=excluded.contact",
            (tg_id, name, contact),
        )
        await db.commit()


async def get_company_by_tg(tg_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, tg_id, name, contact FROM companies WHERE tg_id=?", (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "tg_id": row[1], "name": row[2], "contact": row[3]}


async def list_companies() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, tg_id, name, contact FROM companies") as cur:
            rows = await cur.fetchall()
            return [
                {"id": r[0], "tg_id": r[1], "name": r[2], "contact": r[3]} for r in rows
            ]


async def create_request(client_tg_id: int, data: Dict[str, Any]) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        cur = await db.execute(
            "INSERT INTO requests(client_tg_id, status, data_json, created_at) VALUES(?, 'sent', ?, ?)",
            (client_tg_id, json.dumps(data, ensure_ascii=False), now),
        )
        await db.commit()
        return cur.lastrowid


async def get_request(request_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, client_tg_id, status, data_json, created_at FROM requests WHERE id=?",
            (request_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "client_tg_id": row[1],
                "status": row[2],
                "data": json.loads(row[3]),
                "created_at": row[4],
            }


async def list_requests_by_client(client_tg_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, status, data_json, created_at FROM requests WHERE client_tg_id=? ORDER BY id DESC",
            (client_tg_id,),
        ) as cur:
            rows = await cur.fetchall()
            result = []
            for r in rows:
                result.append(
                    {
                        "id": r[0],
                        "status": r[1],
                        "data": json.loads(r[2]),
                        "created_at": r[3],
                    }
                )
            return result


async def upsert_offer(
    request_id: int, company_id: int, price: str, comment: str | None
):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            "INSERT INTO offers(request_id, company_id, price, comment, created_at) VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(request_id, company_id) DO UPDATE SET price=excluded.price, comment=excluded.comment",
            (request_id, company_id, price, comment, now),
        )
        await db.commit()


async def list_offers(request_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT o.price, o.comment, o.created_at, c.name, c.contact
            FROM offers o
            JOIN companies c ON c.id = o.company_id
            WHERE o.request_id=?
            ORDER BY o.id DESC
        """,
            (request_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [
                {
                    "price": r[0],
                    "comment": r[1],
                    "created_at": r[2],
                    "company_name": r[3],
                    "company_contact": r[4],
                }
                for r in rows
            ]