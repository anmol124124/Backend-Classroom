# Import tools to create WebSocket routes and handle disconnects
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import the connection manager that handles rooms & users
from signaling import manager
from auth import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from database import SessionLocal
from models import User

# Create a router for websocket endpoints
router = APIRouter(
    prefix="/ws",          # All websocket URLs will start with /ws
    tags=["signaling"]     # Group name shown in docs
)

# WebSocket endpoint for a specific meeting room
@router.websocket("/{room_id}")
async def websocket_signaling(websocket: WebSocket, room_id: str, token: str = None):
    # If token is not provided in query params, check headers (though usually query is safer for browser WS)
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=4001) # Unauthorized
        return

    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            await websocket.close(code=4001)
            return
            
        # Verify user exists in DB
        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        db.close()
        
        if not user:
            await websocket.close(code=4001)
            return

        # Explicitly set identity from token
        username = user.username
        role = user.role
        user_id = str(user.id)

    except JWTError:
        await websocket.close(code=4001)
        return

    # Connect the user to the room
    stable_peer_id = await manager.connect(room_id, websocket, user_id=user_id, username=username, role=role)

    try:
        # Keep listening for messages forever while connected
        while True:

            # Receive message from frontend in JSON format
            data = await websocket.receive_json()
            
            # Add sender ID so others know who sent the message
            data["sender_id"] = stable_peer_id
            
            # ========== WHEN USER JOINS ==========
            if data.get("type") == "join":
                # Use authenticated info from token instead of message data
                data["username"] = username
                data["role"] = role
                data["userId"] = user_id
                
                # Check for modes etc from message
                mode = data.get("mode", "normal")

                # CHECK IF ALREADY APPROVED (Seamless Re-join) or HAS HOST PRIVILEGES
                is_host = role in ["admin", "tutor"]
                is_already_approved = room_id in manager.rooms and user_id in manager.rooms[room_id]["approved_users"]
                
                # IF HOST or PREVIOUSLY APPROVED -> Join normally via approved flow
                if is_host or is_already_approved:
                    print(f"User {user_id} ({role}) approved for room {room_id}. Sending join-approved.")
                    await websocket.send_json({
                        "type": "join-approved"
                    })

                # IF NEW STUDENT -> Move to Waiting Room
                else:
                    mode = data.get("mode", "normal")
                    await manager.move_to_waiting(room_id, user_id, websocket, username, role, mode)
                    
                    # Notify admins in the room
                    await manager.broadcast(room_id, {
                        "type": "join-request",
                        "userId": user_id,
                        "username": username
                    }, only_admins=True)
                    
                    # Tell student they are waiting
                    await websocket.send_json({
                        "type": "waiting-for-approval"
                    })

                continue

            # ========== MEDIA READY (Student finished camera initialization) ==========
            if data.get("type") == "media-ready":
                # Use verified info
                data["username"] = username
                data["role"] = role
                data["userId"] = user_id

                # Finalize the transition to 'peers'
                # (Removing from waiting list if they were there)
                # We need to remember the mode they had in waiting
                waiting_user = manager.rooms.get(room_id, {}).get("waiting", {}).get(user_id, {})
                mode = waiting_user.get("mode", "normal")
                
                manager.disconnect(room_id, user_id, websocket) 
                await manager.add_to_peers(room_id, user_id, websocket, username, role, mode)
                
                # Broadast updated participants list to everyone (including self)
                users, presenter = manager.get_participants(room_id)
                await manager.broadcast(room_id, {
                    "type": "participants",
                    "users": users,
                    "presenter": presenter
                })

                # Notify others to start WebRTC
                await manager.broadcast(room_id, {
                    "type": "join",
                    "sender_id": user_id,
                    "username": username
                }, sender_id=user_id)
                
                # Send chat history to the newly joined peer
                history = manager.get_messages(room_id)
                if history:
                    await websocket.send_json({
                        "type": "chat-history",
                        "history": history
                    })
                
                # For Hosts (Admin/Tutor), also send the current waiting room list
                if role in ["admin", "tutor"]:
                    waiting_users = manager.get_waiting_users(room_id)
                    if waiting_users:
                        await websocket.send_json({
                            "type": "waiting-users-list",
                            "users": waiting_users
                        })
                continue

            # ========== ADMIN APPROVE USER ==========
            if data.get("type") == "approve-user":
                sender_info = manager.rooms.get(room_id, {}).get("peers", {}).get(stable_peer_id, {})
                if sender_info.get("role") in ["admin", "tutor"]:
                    target_id = data.get("targetUserId")
                    waiting_user = manager.rooms.get(room_id, {}).get("waiting", {}).get(target_id)
                    
                    if waiting_user:
                        # Move from waiting to peers
                        target_socket = waiting_user["socket"]
                        target_username = waiting_user["username"]
                        target_role = waiting_user["role"]
                        
                    if waiting_user:
                        # Allow seamless re-join in the future by adding to approved_users
                        manager.rooms[room_id]["approved_users"].add(target_id)
                        
                        # Just notify the student to start their media.
                        # They will send 'media-ready' when done, which triggers final join.
                        await target_socket.send_json({
                            "type": "join-approved"
                        })
                continue

            # ========== ADMIN REJECT USER ==========
            if data.get("type") == "reject-user":
                sender_info = manager.rooms.get(room_id, {}).get("peers", {}).get(stable_peer_id, {})
                if sender_info.get("role") in ["admin", "tutor"]:
                    target_id = data.get("targetUserId")
                    await manager.kick_user(room_id, target_id)
                continue

            # ========== SCREEN SHARE EVENT ==========
            if data.get("type") == "screen-share":
                if data.get("isSharing"):
                    manager.set_presenter(room_id, stable_peer_id)
                else:
                    users, presenter = manager.get_participants(room_id)
                    if presenter == stable_peer_id:
                        manager.set_presenter(room_id, None)

                # Broadcast sync
                users, presenter = manager.get_participants(room_id)
                await manager.broadcast(room_id, {
                    "type": "participants",
                    "users": users,
                    "presenter": presenter
                })
                continue

            elif data.get("type") == "screen-share-started":
                manager.set_presenter(room_id, stable_peer_id)
                users, presenter = manager.get_participants(room_id)
                await manager.broadcast(room_id, {
                    "type": "participants",
                    "users": users,
                    "presenter": presenter
                })
                # Also broadcast the original message so everyone starts their PC if needed
                await manager.broadcast(room_id, data, sender_id=stable_peer_id)
                continue

            elif data.get("type") == "screen-share-stopped":
                users, presenter = manager.get_participants(room_id)
                if presenter == stable_peer_id:
                    manager.set_presenter(room_id, None)
                
                users, presenter = manager.get_participants(room_id)
                await manager.broadcast(room_id, {
                    "type": "participants",
                    "users": users,
                    "presenter": presenter
                })
                # Also broadcast the original message
                await manager.broadcast(room_id, data, sender_id=stable_peer_id)
                continue

            # ========== CHAT MESSAGE ==========
            elif data.get("type") == "chat-message":

                # Save message to history
                manager.add_message(room_id, data)

                # Send message to everyone in the room
                await manager.broadcast(room_id, data)

                continue

            # ========== ADMIN KICK USER ==========
            elif data.get("type") == "kick-user":

                # Get info about sender
                sender_info = manager.rooms.get(room_id, {}).get("peers", {}).get(stable_peer_id, {})

                # Only admin or tutor can kick users
                if sender_info.get("role") in ["admin", "tutor"]:

                    # ID of user to remove
                    target_id = data.get("targetUserId")

                    # Get username of removed user
                    target_username = manager.rooms.get(room_id, {}).get("peers", {}).get(target_id, {}).get("username", "Unknown")

                    # Remove user from room
                    await manager.kick_user(room_id, target_id)
                    
                    # Notify others that user was removed
                    await manager.broadcast(room_id, {
                        "type": "user-kicked-notification",
                        "username": target_username,
                        "message": f"{target_username} was removed by admin"
                    })
                    
                    # Send updated participants list
                    users, presenter = manager.get_participants(room_id)
                    await manager.broadcast(room_id, {
                        "type": "participants",
                        "users": users,
                        "presenter": presenter
                    })

                continue

            # ========== PRIVATE MESSAGE (WebRTC signaling) ==========
            # If message has a target user → send only to them
            target_id = data.get("target_id")

            if target_id:
                await manager.send_to_target(room_id, target_id, data)

            else:
                # Otherwise send to everyone except sender
                await manager.broadcast(room_id, data, sender_id=stable_peer_id)
            
    # ========== USER DISCONNECTED ==========
    except WebSocketDisconnect:
        # Remove user from room and only broadcast if they were actually removed
        # (prevents redundant 'leave' when session is replaced by a newer tab)
        if manager.disconnect(room_id, stable_peer_id, websocket):
            # Get updated participants
            users, presenter = manager.get_participants(room_id)

            # Notify everyone about new participant list
            await manager.broadcast(room_id, {
                "type": "participants",
                "users": users,
                "presenter": presenter
            })

            # Notify that user left
            await manager.broadcast(room_id, {
                "type": "leave",
                "sender_id": stable_peer_id,
                "message": f"User {stable_peer_id} has left the room"
            })

    # ========== HANDLE ERRORS ==========
    except Exception as e:
        print(f"WebSocket error: {e}")   # print error in console
        manager.disconnect(room_id, stable_peer_id, websocket)  # safely remove user