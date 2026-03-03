# used to generate unique IDs for users
import uuid

# used for type hinting (better readability & autocomplete)
from typing import Dict, List

# WebSocket object used to send/receive real-time messages
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Stores all active rooms and users inside them
        # Structure:
        # rooms = {
        #   room_id: {
        #       "peers": { ... },     # approved users
        #       "waiting": {          # users waiting for approval
        #           peer_id: {
        #               "socket": WebSocket,
        #               "username": str,
        #               "role": str
        #           }
        #       },
        #       "presenter": peer_id,
        #       "messages": [],
        #       "approved_users": set()  # persistent approval for the session
        #   }
        # }
        self.rooms: Dict[str, dict] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        # Accept the WebSocket connection
        await websocket.accept()
        
        # If room doesn't exist, create it
        if room_id not in self.rooms:
            self.rooms[room_id] = {
                "peers": {},        # approved users
                "waiting": {},      # users waiting for approval
                "presenter": None,
                "messages": [],
                "approved_users": set()
            }
        
        # We assign a temporary ID until the 'join' message provides the stable ID
        temp_peer_id = str(uuid.uuid4())
        
        # Send the assigned temporary peer ID (just for initial identification)
        await websocket.send_json({
            "type": "init",
            "peer_id": temp_peer_id
        })
        
        return temp_peer_id

    async def move_to_waiting(self, room_id: str, peer_id: str, websocket: WebSocket, username: str, role: str):
        # Add user to waiting list, replacing existing session if found
        if room_id in self.rooms:
            # Check if this user already has a session (anywhere)
            await self._ensure_single_session(room_id, peer_id)
            
            self.rooms[room_id]["waiting"][peer_id] = {
                "socket": websocket,
                "username": username,
                "role": role
            }

    async def add_to_peers(self, room_id: str, peer_id: str, websocket: WebSocket, username: str, role: str):
        # Add user to approved peers list, replacing existing session if found
        if room_id in self.rooms:
            # Check if this user already has a session (anywhere)
            await self._ensure_single_session(room_id, peer_id)
            
            self.rooms[room_id]["peers"][peer_id] = {
                "socket": websocket,
                "username": username,
                "role": role
            }
            # Record that this user is approved for this room session
            self.rooms[room_id]["approved_users"].add(peer_id)

    async def _ensure_single_session(self, room_id: str, peer_id: str):
        """Internal helper to close any existing session for a user ID."""
        if room_id not in self.rooms:
            return

        # Check peers
        if peer_id in self.rooms[room_id]["peers"]:
            old_info = self.rooms[room_id]["peers"][peer_id]
            
            # If the session we're replacing was the presenter, clear it
            if self.rooms[room_id].get("presenter") == peer_id:
                self.rooms[room_id]["presenter"] = None

            try:
                await old_info["socket"].send_json({
                    "type": "kicked",
                    "reason": "session-replaced",
                    "message": "You joined from another tab. This session has been disconnected."
                })
                await old_info["socket"].close()
            except Exception:
                pass
            del self.rooms[room_id]["peers"][peer_id]

        # Check waiting
        if peer_id in self.rooms[room_id]["waiting"]:
            old_info = self.rooms[room_id]["waiting"][peer_id]
            try:
                await old_info["socket"].send_json({
                    "type": "kicked",
                    "reason": "session-replaced",
                    "message": "You joined from another tab. This session has been disconnected."
                })
                await old_info["socket"].close()
            except Exception:
                pass
            del self.rooms[room_id]["waiting"][peer_id]

    def update_user_info(self, room_id: str, peer_id: str, username: str, role: str = "student"):
        # Update username and role after user joins (for already approved peers)
        if room_id in self.rooms and peer_id in self.rooms[room_id]["peers"]:
            self.rooms[room_id]["peers"][peer_id]["username"] = username
            self.rooms[room_id]["peers"][peer_id]["role"] = role

    def get_participants(self, room_id: str):
        # Return list of APPROVED users in a room
        if room_id in self.rooms:
            participants = [
                {
                    "userId": pid,
                    "username": info["username"],
                    "role": info.get("role", "student")
                }
                for pid, info in self.rooms[room_id]["peers"].items()
            ]

            # Also return who is presenting
            return participants, self.rooms[room_id].get("presenter")

        return [], None

    def get_waiting_users(self, room_id: str):
        # Return list of users waiting for approval
        if room_id in self.rooms:
            return [
                {
                    "userId": pid,
                    "username": info["username"]
                }
                for pid, info in self.rooms[room_id]["waiting"].items()
            ]
        return []

    def get_admins(self, room_id: str):
        # Get list of admin peer IDs in the room
        if room_id in self.rooms:
            return [pid for pid, info in self.rooms[room_id]["peers"].items() if info.get("role") == "admin"]
        return []

    def set_presenter(self, room_id: str, peer_id: str):
        # Set who is sharing screen
        if room_id in self.rooms:
            self.rooms[room_id]["presenter"] = peer_id

    def add_message(self, room_id: str, message: dict):
        # Save chat message to room history
        if room_id in self.rooms:
            self.rooms[room_id]["messages"].append(message)

    def get_messages(self, room_id: str):
        # Return chat history of the room
        if room_id in self.rooms:
            return self.rooms[room_id]["messages"]
        return []

    def disconnect(self, room_id: str, peer_id: str, websocket: WebSocket = None):
        # Remove user when they leave (check both peers and waiting)
        if room_id in self.rooms:
            # check peers
            if peer_id in self.rooms[room_id]["peers"]:
                # ONLY disconnect if the websocket matches (to avoid race conditions)
                if websocket and self.rooms[room_id]["peers"][peer_id]["socket"] != websocket:
                    return False

                del self.rooms[room_id]["peers"][peer_id]
                # if presenter left → remove presenter
                if self.rooms[room_id]["presenter"] == peer_id:
                    self.rooms[room_id]["presenter"] = None
                
                # if no one left (neither peers nor waiting) → delete the room
                if not self.rooms[room_id]["peers"] and not self.rooms[room_id]["waiting"]:
                    del self.rooms[room_id]
                return True
            
            # check waiting
            elif peer_id in self.rooms[room_id]["waiting"]:
                # ONLY disconnect if the websocket matches
                if websocket and self.rooms[room_id]["waiting"][peer_id]["socket"] != websocket:
                    return False

                del self.rooms[room_id]["waiting"][peer_id]

                # if no one left (neither peers nor waiting) → delete the room
                if not self.rooms[room_id]["peers"] and not self.rooms[room_id]["waiting"]:
                    del self.rooms[room_id]
                return True
        return False

    async def send_to_target(self, room_id: str, target_id: str, message: dict):
        # Send message to a specific user (check both lists)
        if room_id in self.rooms:
            info = self.rooms[room_id]["peers"].get(target_id) or self.rooms[room_id]["waiting"].get(target_id)
            if info:
                try:
                    await info["socket"].send_json(message)
                except Exception:
                    pass

    async def broadcast(self, room_id: str, message: dict, sender_id: str = None, only_admins: bool = False):
        # Send message to EVERYONE APPROVED in the room
        if room_id in self.rooms:
            for peer_id, info in self.rooms[room_id]["peers"].items():
                if peer_id != sender_id:
                    if only_admins and info.get("role") != "admin":
                        continue
                    try:
                        await info["socket"].send_json(message)
                    except Exception:
                        pass

    async def kick_user(self, room_id: str, target_id: str):
        # Remove a user from the room (works for both peers and waiting)
        if room_id in self.rooms:
            info = self.rooms[room_id]["peers"].get(target_id) or self.rooms[room_id]["waiting"].get(target_id)
            if info:
                try:
                    await info["socket"].send_json({
                        "type": "kicked",
                        "message": "You were removed or rejected by the host"
                    })
                    await info["socket"].close()
                except Exception:
                    pass
                self.disconnect(room_id, target_id)

# Create a global manager instance used by websocket routes
manager = ConnectionManager()