import logging
from fastapi import APIRouter, HTTPException
from app.db.database import get_connection
from app.models.schemas import AgentCreate, HandoffCreate
from app.services.security import redact_secrets

import sqlite3

router = APIRouter()

logger = logging.getLogger(__name__)


def _normalize_child_ids(parent_agent_id: int, child_agent_ids: list[int]) -> tuple[list[int] | None, str | None]:
    """Deduplicate children, reject self-handoff. Returns (ids, error_message)."""
    seen = set()
    unique: list[int] = []
    for cid in child_agent_ids:
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(cid)
    if parent_agent_id in seen:
        return None, "Cannot hand off to the same agent you are editing"
    return unique, None


def _verify_agents_exist(cursor, ids: list[int]) -> str | None:
    if not ids:
        return None
    placeholders = ",".join("?" * len(ids))
    cursor.execute(f"SELECT id FROM agents WHERE id IN ({placeholders})", ids)
    found = {row["id"] for row in cursor.fetchall()}
    missing = [i for i in ids if i not in found]
    if missing:
        return f"Unknown agent id(s): {missing}"
    return None


# -----------------------------
# CREATE AGENT
# -----------------------------
@router.post("/agents")
def create_agent(data: AgentCreate):
    redacted_payload = {
        "name": data.name,
        "prompt": redact_secrets(data.prompt),
        "type": data.type,
        "data_file": data.data_file,
    }
    logger.info(f"[CREATE AGENT] Incoming request: {redacted_payload}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO agents (name, prompt, type, data_file)
            VALUES (?, ?, ?, ?)
        """, (data.name, data.prompt, data.type, data.data_file))

        conn.commit()
        agent_id = cursor.lastrowid

        return {
            "message": "Agent created",
            "id": agent_id
        }

    #  HANDLE UNIQUE ERROR PROPERLY
    except sqlite3.IntegrityError as e:
        logger.error(f"[CREATE AGENT] Duplicate name: {str(e)}")

        raise HTTPException(
            status_code=409,
            detail="An agent with this name already exists. Please choose a different name"
        )

    #  HANDLE OTHER ERRORS
    except Exception as e:
        logger.error(f"[CREATE AGENT] Failed - Error: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

    finally:
        conn.close()
        logger.info("[CREATE AGENT] DB connection closed")

# -----------------------------
# EDIT AGENT
# -----------------------------
@router.put("/agents/{agent_id}")
def edit_agent(agent_id: int, data: AgentCreate):
    logger.info(
        f"[EDIT AGENT] Agent ID={agent_id} Incoming request: "
        f"{{'name': {data.name!r}, 'prompt': {redact_secrets(data.prompt)!r}, "
        f"'type': {data.type!r}, 'data_file': {data.data_file!r}}}"
    )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 🔍 Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        # 🔄 Try update
        cursor.execute(
            """
            UPDATE agents
            SET name = ?, prompt = ?, type = ?, data_file = ?
            WHERE id = ?
            """,
            (data.name, data.prompt, data.type, data.data_file, agent_id),
        )

        conn.commit()

        return {"message": "Agent updated", "id": agent_id}

    # Handle duplicate name
    except sqlite3.IntegrityError as e:
        logger.error(f"[EDIT AGENT] Duplicate name: {str(e)}")

        raise HTTPException(
            status_code=409,
            detail="An agent with this name already exists. Please choose a different name"
        )

    #  Handle other errors
    except Exception as e:
        logger.error(f"[EDIT AGENT] Failed - Error: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Failed to update agent"
        )

    finally:
        conn.close()
        logger.info("[EDIT AGENT] DB connection closed")

# -----------------------------
# LIST AGENTS
# -----------------------------
@router.get("/agents")
def list_agents():
    logger.info("[LIST AGENTS] Fetching all agents")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM agents")
        rows = cursor.fetchall()

        agents = [dict(row) for row in rows]

        logger.info(f"[LIST AGENTS] Retrieved {len(agents)} agents")

        return {"agents": agents}

    except Exception as e:
        logger.error(f"[LIST AGENTS] Failed - Error: {str(e)}", exc_info=True)
        return {"error": "Failed to fetch agents"}

    finally:
        conn.close()
        logger.info("[LIST AGENTS] DB connection closed")


# -----------------------------
# GET ONE AGENT (for edit forms: includes current handoffs)
# -----------------------------
@router.get("/agents/{agent_id}")
def get_agent(agent_id: int):
    logger.info(f"[GET AGENT] id={agent_id}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": "Agent not found"}

        cursor.execute(
            """
            SELECT child_agent_id FROM agent_handoffs
            WHERE parent_agent_id = ?
            ORDER BY child_agent_id
            """,
            (agent_id,),
        )
        child_agent_ids = [r["child_agent_id"] for r in cursor.fetchall()]

        agent = dict(row)
        return {
            "agent": agent,
            "child_agent_ids": child_agent_ids,
        }

    except Exception as e:
        logger.error(f"[GET AGENT] Failed - Error: {str(e)}", exc_info=True)
        return {"error": "Failed to fetch agent"}

    finally:
        conn.close()
        logger.info("[GET AGENT] DB connection closed")


# -----------------------------
# ADD HANDOFFS
# -----------------------------
@router.post("/agents/{agent_id}/handoffs")
def add_handoffs(agent_id: int, data: HandoffCreate):
    logger.info(f"[ADD HANDOFFS] Parent Agent: {agent_id}")
    logger.info(f"[ADD HANDOFFS] Children: {data.child_agent_ids}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            return {"error": "Agent not found"}

        child_ids, err = _normalize_child_ids(agent_id, data.child_agent_ids)
        if err:
            return {"error": err}

        err = _verify_agents_exist(cursor, child_ids)
        if err:
            return {"error": err}

        for child_id in child_ids:
            logger.info(f"[ADD HANDOFFS] Linking {agent_id} -> {child_id}")
            cursor.execute(
                """
                SELECT 1 FROM agent_handoffs
                WHERE parent_agent_id = ? AND child_agent_id = ?
                """,
                (agent_id, child_id),
            )
            if cursor.fetchone():
                continue
            cursor.execute(
                """
                INSERT INTO agent_handoffs (parent_agent_id, child_agent_id)
                VALUES (?, ?)
                """,
                (agent_id, child_id),
            )

        conn.commit()

        logger.info(f"[ADD HANDOFFS] Success for parent {agent_id}")

        return {"message": "Handoffs added"}

    except Exception as e:
        logger.error(f"[ADD HANDOFFS] Failed - Error: {str(e)}", exc_info=True)
        return {"error": "Failed to add handoffs"}

    finally:
        conn.close()
        logger.info("[ADD HANDOFFS] DB connection closed")


# -----------------------------
# REPLACE HANDOFFS (use when editing: set full child list)
# -----------------------------
@router.put("/agents/{agent_id}/handoffs")
def set_handoffs(agent_id: int, data: HandoffCreate):
    logger.info(f"[SET HANDOFFS] Parent Agent: {agent_id}")
    logger.info(f"[SET HANDOFFS] Children: {data.child_agent_ids}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            return {"error": "Agent not found"}

        child_ids, err = _normalize_child_ids(agent_id, data.child_agent_ids)
        if err:
            return {"error": err}

        err = _verify_agents_exist(cursor, child_ids)
        if err:
            return {"error": err}

        cursor.execute(
            "DELETE FROM agent_handoffs WHERE parent_agent_id = ?",
            (agent_id,),
        )
        for child_id in child_ids:
            cursor.execute(
                """
                INSERT INTO agent_handoffs (parent_agent_id, child_agent_id)
                VALUES (?, ?)
                """,
                (agent_id, child_id),
            )

        conn.commit()
        logger.info(f"[SET HANDOFFS] Success for parent {agent_id}")
        return {"message": "Handoffs updated", "child_agent_ids": child_ids}

    except Exception as e:
        logger.error(f"[SET HANDOFFS] Failed - Error: {str(e)}", exc_info=True)
        return {"error": "Failed to update handoffs"}

    finally:
        conn.close()
        logger.info("[SET HANDOFFS] DB connection closed")

# -----------------------------
# CLEAR DATABASE
# -----------------------------
@router.delete("/agents")
def clear_database():
    logger.warning("[CLEAR DATABASE] Deleting ALL agents and handoffs")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Delete all handoffs first
        cursor.execute("DELETE FROM agent_handoffs")

        # Delete all agents
        cursor.execute("DELETE FROM agents")

        conn.commit()

        logger.warning("[CLEAR DATABASE] All data deleted")

        return {"message": "All agents and handoffs deleted"}

    except Exception as e:
        logger.error(f"[CLEAR DATABASE] Failed - Error: {str(e)}", exc_info=True)
        return {"error": "Failed to clear database"}

    finally:
        conn.close()
        logger.info("[CLEAR DATABASE] DB connection closed")

# -----------------------------
# DELETE SPECIFIC AGENT
# -----------------------------
@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: int):
    logger.warning(f"[DELETE AGENT] Request to delete agent ID={agent_id}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            return {"error": "Agent not found"}

        # Delete related handoffs first (to maintain integrity)
        cursor.execute(
            "DELETE FROM agent_handoffs WHERE parent_agent_id = ? OR child_agent_id = ?",
            (agent_id, agent_id),
        )

        # Delete the agent
        cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))

        conn.commit()

        logger.warning(f"[DELETE AGENT] Successfully deleted agent ID={agent_id}")

        return {"message": f"Agent {agent_id} deleted successfully"}

    except Exception as e:
        logger.error(f"[DELETE AGENT] Failed - Error: {str(e)}", exc_info=True)
        return {"error": "Failed to delete agent"}

    finally:
        conn.close()
        logger.info("[DELETE AGENT] DB connection closed")