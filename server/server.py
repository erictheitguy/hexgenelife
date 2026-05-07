import asyncio
import json
import os
import sqlite3
import datetime
import time
import websockets
import math
import logging
import subprocess
import sys

from multiprocessing import Queue

from server.constants import (HEX_RADIUS, HEX_CREATION_BROADCAST_RANGE, DEFAULT_WATER, DEFAULT_GRASS,
                       DEFAULT_MOB_PHYSICAL, DEFAULT_MOB_HEALTH_EXT, DEFAULT_DECISION_TREE,
                       axial_to_pixel_flat_top, pixel_to_axial_flat_top, get_hex_corners)
from server.db_init import DatabaseInitializer
from server.validators import MessageValidator
from server.mob_manager import MobManager
from server.mob_interactions import MobInteractions
from server.environment.grass_process import GrassProcess
from server.environment.rain_process import RainProcess

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "server.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Server")

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.db")
MAX_ACTIONS_PER_TICK = 3

class GameServer:
    def __init__(self, db_path=_DEFAULT_DB):
        self.db_path = db_path
        self.db_conn = None
        self.clients = set()
        self.action_queue = []          
        self.tick_rate = 1.0            
        self._client_action_counts = {}  
        self._ws_to_mob = {}             
        self.pending_child_spawns: list[str] = []  # child mob_ids awaiting client launch
        
        self.db_conn = sqlite3.connect(self.db_path)
        self.db_conn.execute("PRAGMA journal_mode=WAL")
        DatabaseInitializer.initialize_db(self.db_conn)
        
        self.mob_manager = MobManager(self.db_conn)
        self.mob_interactions = MobInteractions(self, self.db_conn, self.mob_manager)
        
        self.tick_queue = Queue()
        self.grass_process = GrassProcess(self.db_path, self.tick_queue)
        self.rain_process = RainProcess(self.db_path, self.tick_queue)
        
        logger.info("GameServer initialized. Database connection established.")

    async def send_error(self, websocket, error_code: str, error_message: str):
        err_msg = json.dumps({
            "type": "ERROR",
            "payload": {
                "errorCode": error_code,
                "errorMessage": error_message,
            },
        })
        try:
            await websocket.send(err_msg)
        except Exception:
            pass

    async def broadcast(self, message_type: str, payload: dict):
        if not self.clients:
            return
        msg = json.dumps({"type": message_type, "payload": payload})
        for client in list(self.clients):
            try:
                await client.send(msg)
            except Exception:
                pass

    async def ws_handler(self, websocket, path="/"):
        self.clients.add(websocket)
        self._client_action_counts[websocket] = 0
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    command_type = message.get("type")
                    payload = message.get("payload", message.get("data", {}))

                    client_id = payload.get("clientId") or payload.get("client_id")
                    if client_id:
                        self.mob_manager.ensure_client_mob(client_id)
                        mob_id = f"mob_{client_id}"
                        if self._ws_to_mob.get(websocket) != mob_id:
                            self._ws_to_mob[websocket] = mob_id
                            cursor = self.db_conn.cursor()
                            cursor.execute("UPDATE mobs SET is_active = 1 WHERE mob_id = ?", (mob_id,))
                            self.db_conn.commit()

                    if not MessageValidator.validate_message(message, command_type):
                        await self.send_error(
                            websocket, "VALIDATION_FAILED",
                            "Message schema validation failed."
                        )
                        continue

                    count = self._client_action_counts.get(websocket, 0)
                    if count >= MAX_ACTIONS_PER_TICK:
                        await self.send_error(
                            websocket, "ACTION_LIMIT_EXCEEDED",
                            f"Maximum {MAX_ACTIONS_PER_TICK} actions allowed per tick."
                        )
                        continue

                    self._client_action_counts[websocket] = count + 1
                    self.action_queue.append({
                        "websocket": websocket,
                        "command_type": command_type,
                        "payload": payload,
                    })

                except json.JSONDecodeError:
                    logger.error("Error: Malformed JSON received.")
                    await self.send_error(
                        websocket, "MALFORMED_JSON", "Invalid JSON payload."
                    )
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected.")
        finally:
            self.clients.discard(websocket)
            self._client_action_counts.pop(websocket, None)
            mob_id = self._ws_to_mob.pop(websocket, None)
            if mob_id and self.db_conn:
                cursor = self.db_conn.cursor()
                cursor.execute("UPDATE mobs SET is_active = 0 WHERE mob_id = ?", (mob_id,))
                self.db_conn.commit()

    async def _tick_loop(self):
        logger.info(f"Tick loop starting. Tick rate: {self.tick_rate}s")
        tick_num = 0
        while True:
            await asyncio.sleep(self.tick_rate)
            tick_start = time.perf_counter()
            tick_num += 1

            # --- Phase: action processing ---
            t0 = time.perf_counter()
            action_counts: dict[str, int] = {}
            if self.action_queue:
                queue_snapshot = self.action_queue[:]
                self.action_queue.clear()

                for action in queue_snapshot:
                    cmd = action["command_type"]
                    payload = action["payload"]
                    ws = action["websocket"]
                    action_counts[cmd] = action_counts.get(cmd, 0) + 1

                    if cmd == "MOVE_MOB":
                        await self.mob_interactions.handle_move_mob(payload, ws)
                    elif cmd == "REQUEST_WORLD_STATE":
                        await self._handle_request_world_state(payload, ws)
                    elif cmd == "LOOK":
                        await self.mob_interactions.handle_look(payload, ws)
                    elif cmd == "EAT_GRASS":
                        await self.mob_interactions.handle_eat_grass(payload, ws)
                    elif cmd == "ATTACK_MOB":
                        await self.mob_interactions.handle_attack_mob(payload, ws)
                    elif cmd == "EAT_MOB":
                        await self.mob_interactions.handle_eat_mob(payload, ws)
                    elif cmd == "BREED":
                        await self.mob_interactions.handle_breed(payload, ws)
                    elif cmd == "REQUEST_BRAIN_FUNCTIONS":
                        await self._handle_request_brain_functions(payload, ws)
                    else:
                        logger.warning(f"Unknown command queued: {cmd}")
            t_actions = time.perf_counter() - t0

            # --- Phase: metabolism ---
            t0 = time.perf_counter()
            await self.mob_interactions.process_metabolism()
            t_metabolism = time.perf_counter() - t0

            # --- Phase: spawn child clients ---
            await self._flush_pending_child_spawns()

            # --- Phase: broadcast / reset ---
            t0 = time.perf_counter()
            for ws in list(self._client_action_counts):
                self._client_action_counts[ws] = 0
            self.tick_queue.put("TICK")
            cursor = self.db_conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO server_state (key, value) VALUES ('tick_num', ?)",
                (str(tick_num),)
            )
            self.db_conn.commit()
            await self.broadcast("TICK_COMPLETE", {"timestamp": time.time()})
            t_broadcast = time.perf_counter() - t0

            t_total = time.perf_counter() - tick_start
            logger.debug(
                f"[TICK {tick_num}] total={t_total*1000:.1f}ms  "
                f"actions={t_actions*1000:.1f}ms({sum(action_counts.values())} cmds {action_counts})  "
                f"metabolism={t_metabolism*1000:.1f}ms  "
                f"broadcast={t_broadcast*1000:.1f}ms"
            )
            if t_total > self.tick_rate * 0.8:
                logger.warning(
                    f"[TICK {tick_num}] Slow tick: {t_total*1000:.1f}ms "
                    f"(>{self.tick_rate*800:.0f}ms threshold). "
                    f"actions={t_actions*1000:.1f}ms  metabolism={t_metabolism*1000:.1f}ms  "
                    f"broadcast={t_broadcast*1000:.1f}ms"
                )

    async def _flush_pending_child_spawns(self):
        """Launch a client process for every child mob queued since the last tick."""
        if not self.pending_child_spawns:
            return

        # Resolve the project root: two levels up from server/server.py
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = os.environ.copy()
        env["PYTHONPATH"] = root_dir

        for child_mob_id in self.pending_child_spawns:
            # client_id is the mob_id without the leading "mob_" prefix so
            # the server's ensure_client_mob logic maps it back to mob_<client_id>.
            # Child mobs are created with the full ID (e.g. mob_child_<uuid>),
            # so we pass the full mob_id and use --mobs to tell the client
            # exactly which mob to manage.
            client_id = child_mob_id  # use full id as client key
            cmd = [
                sys.executable, "-m", "client.websocket_client",
                client_id,
                "--mobs", child_mob_id,
            ]
            try:
                subprocess.Popen(cmd, env=env, cwd=root_dir)
                logger.info(f"Spawned client process for child mob {child_mob_id}")
            except Exception as exc:
                logger.error(f"Failed to spawn client for child mob {child_mob_id}: {exc}")

        self.pending_child_spawns.clear()

    async def _handle_request_world_state(self, payload: dict, ws):
        client_id = payload.get("clientId") or payload.get("client_id")
        if not client_id:
            return
        if not self.db_conn:
            return

        cursor = self.db_conn.cursor()

        cursor.execute("SELECT * FROM mobs")
        raw_mobs = cursor.fetchall()
        mobs = []
        for m in raw_mobs:
            mob_dict = dict(m)
            mob_id = m["mob_id"]
            if isinstance(mob_dict.get("position"), str):
                mob_dict["position"] = json.loads(mob_dict["position"])
            mob_dict["health"] = self.mob_manager.get_mob_health(mob_id)
            mob_dict["physical"] = self.mob_manager.get_mob_physical(mob_id)
            mob_dict["species"] = self.mob_manager.get_species_info(mob_id)
            brain_data = self.mob_manager.get_mob_brain(mob_id)
            mob_dict["brain"] = {
                "decision_tree": brain_data.get("decision_tree", {}),
                "memory": brain_data.get("memory", {})
            }
            mobs.append(mob_dict)

        cursor.execute("SELECT * FROM hex_tiles")
        tiles = []
        for row in cursor.fetchall():
            r = dict(row)
            tiles.append({
                "hexId": str(r["id"]),
                "tileData": {
                    "location": {
                        "centerX": r["centerX"],
                        "centerY": r["centerY"],
                    },
                    "resources": {
                        "water": r["Water"],
                        "grass": r["Grass"],
                    },
                    "updated": r["Updated"],
                },
            })

        try:
            await ws.send(json.dumps({
                "type": "WORLD_UPDATE",
                "payload": {
                    "mobs": mobs,
                    "tiles": tiles,
                },
            }))
        except Exception as e:
            logger.error(f"Failed to send world state: {e}")

    async def _handle_request_brain_functions(self, payload: dict, websocket):
        if not self.db_conn:
            return
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM brain_functions")
        rows = cursor.fetchall()
        
        functions = []
        for row in rows:
            functions.append({
                "function_id": row["function_id"],
                "function_name": row["function_name"],
                "description": row["description"],
                "input_schema": json.loads(row["input_schema"]) if row["input_schema"] else None,
                "output_schema": json.loads(row["output_schema"]) if row["output_schema"] else None,
                "version": row["version"],
            })
            
        try:
            msg = json.dumps({"type": "BRAIN_FUNCTIONS_LIST", "payload": {"functions": functions}})
            await websocket.send(msg)
        except Exception as e:
            logger.error(f"Failed to send BRAIN_FUNCTIONS_LIST: {e}")

    async def _create_hex_at(self, q: int, r: int):
        if not self.db_conn:
            return
        cursor = self.db_conn.cursor()
        
        cursor.execute("SELECT id FROM hex_tiles WHERE q = ? AND r = ?", (q, r))
        if cursor.fetchone():
            return
            
        neighbor_qs = [(q+1, r), (q+1, r-1), (q, r-1), (q-1, r), (q-1, r+1), (q, r+1)]
        water_sum = 0.0
        grass_sum = 0.0
        n_count = 0
        
        where_clauses = ["(q=? AND r=?)" for _ in range(6)]
        query = f"SELECT Water, Grass FROM hex_tiles WHERE {' OR '.join(where_clauses)}"
        params = []
        for nq, nr in neighbor_qs:
            params.extend([nq, nr])
            
        cursor.execute(query, params)
        for row in cursor.fetchall():
            water_sum += row["Water"]
            grass_sum += row["Grass"]
            n_count += 1
            
        if n_count > 0:
            new_water = water_sum / n_count
            new_grass = grass_sum / n_count
        else:
            new_water = DEFAULT_WATER
            new_grass = DEFAULT_GRASS
            
        cx, cy = axial_to_pixel_flat_top(q, r, HEX_RADIUS)
        corners = get_hex_corners(cx, cy, HEX_RADIUS)
        loc_json = json.dumps({"type": "Polygon", "coordinates": [corners]})
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO hex_tiles (
                loc, centerXY, centerX, centerY,
                hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6, hexcp7,
                Water, Grass, Created, Updated, q, r
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc_json, json.dumps([cx, cy]), cx, cy,
            json.dumps(corners[0]), json.dumps(corners[1]), json.dumps(corners[2]),
            json.dumps(corners[3]), json.dumps(corners[4]), json.dumps(corners[5]), json.dumps(corners[6]),
            new_water, new_grass, now, now, q, r
        ))
        
        new_hex_id = cursor.lastrowid
        self.db_conn.commit()
        logger.info(f"Created new hex tile {new_hex_id} at axial ({q}, {r})")
        
        cursor.execute("SELECT mob_id, position FROM mobs")
        targets = set()
        for mob in cursor.fetchall():
            pos = json.loads(mob["position"])
            mx, my = pos.get("x", 0), pos.get("y", 0)
            dist = math.sqrt((mx - cx)**2 + (my - cy)**2)
            if dist <= HEX_CREATION_BROADCAST_RANGE:
                targets.add(mob["mob_id"])
                
        payload = {
            "hexId": str(new_hex_id),
            "tileData": {
                "location": {"centerX": cx, "centerY": cy},
                "corners": {
                    "hexcp1": corners[0], "hexcp2": corners[1], "hexcp3": corners[2],
                    "hexcp4": corners[3], "hexcp5": corners[4], "hexcp6": corners[5], "hexcp7": corners[6]
                },
                "resources": {"water": new_water, "grass": new_grass},
                "created": now,
                "q": q,
                "r": r
            }
        }
        msg = json.dumps({"type": "HEX_CREATED", "payload": payload})
        for ws in self.clients:
            if self._ws_to_mob.get(ws) in targets:
                try:
                    await ws.send(msg)
                except Exception:
                    pass

    async def ensure_hex_layer(self, q: int, r: int, radius: int = 1):
        """Ensure all hexes within radius of (q, r) axial are created."""
        for dq in range(-radius, radius + 1):
            for dr in range(max(-radius, -dq - radius), min(radius, -dq + radius) + 1):
                await self._create_hex_at(q + dq, r + dr)

    # ------------------------------------------------------------------
    # Proxy helpers — keep backward-compat with tests that call these
    # directly on GameServer rather than on the sub-objects.
    # ------------------------------------------------------------------

    def close(self):
        """Alias for stop() — used by test tearDown methods."""
        self.stop()

    def _ensure_client_mob(self, client_id: str, mob_type: str = "prey",
                            physical_overrides: dict | None = None):
        return self.mob_manager.ensure_client_mob(client_id, mob_type, physical_overrides)

    def _get_mob_health(self, mob_id: str) -> dict:
        return self.mob_manager.get_mob_health(mob_id)

    def _get_mob_physical(self, mob_id: str) -> dict:
        return self.mob_manager.get_mob_physical(mob_id)

    def _mob_exists(self, mob_id: str) -> bool:
        return self.mob_manager.mob_exists(mob_id)

    def _classify_mob(self, mob_id: str, parent_species_id=None):
        return self.mob_manager.classify_mob(mob_id, parent_species_id)

    @property
    def _mob_last_move_dist(self) -> dict:
        return self.mob_interactions.mob_last_move_dist

    @_mob_last_move_dist.setter
    def _mob_last_move_dist(self, value: dict):
        self.mob_interactions.mob_last_move_dist = value

    async def _handle_look(self, payload: dict, websocket):
        return await self.mob_interactions.handle_look(payload, websocket)

    async def _handle_eat_grass(self, payload: dict, websocket):
        return await self.mob_interactions.handle_eat_grass(payload, websocket)

    async def _handle_attack_mob(self, payload: dict, websocket):
        return await self.mob_interactions.handle_attack_mob(payload, websocket)

    async def _handle_eat_mob(self, payload: dict, websocket):
        return await self.mob_interactions.handle_eat_mob(payload, websocket)

    async def _handle_breed(self, payload: dict, websocket):
        return await self.mob_interactions.handle_breed(payload, websocket)

    async def _handle_move_mob(self, payload: dict, websocket):
        return await self.mob_interactions.handle_move_mob(payload, websocket)

    async def _process_metabolism(self):
        return await self.mob_interactions.process_metabolism()

    def _validate_message(self, message: dict, command_type: str) -> bool:
        return MessageValidator.validate_message(message, command_type)

    async def _create_adjacent_hex(self, x: float, y: float):
        """Create a hex tile at pixel coordinates (x, y) — used by tests."""
        q, r = pixel_to_axial_flat_top(x, y, HEX_RADIUS)
        await self._create_hex_at(q, r)

    def _get_current_timestamp(self) -> float:
        return time.time()

    async def start(self):
        self.grass_process.start()
        self.rain_process.start()
        async with websockets.serve(self.ws_handler, "localhost", 8765):
            logger.info("WebSocket server started on ws://localhost:8765")
            await self._tick_loop()

    def stop(self):
        try:
            self.tick_queue.put("STOP")
            self.tick_queue.put("STOP")
        except:
            pass
            
        if self.grass_process.is_alive():
            self.grass_process.join(timeout=2)
        if self.rain_process.is_alive():
            self.rain_process.join(timeout=2)

        if self.db_conn:
            self.db_conn.close()
            logger.info("Database connection closed.")


if __name__ == "__main__":
    server = GameServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("\nServer shutting down.")
    finally:
        server.stop()
