# Import tools to create WebSocket routes and handle disconnects
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import the connection manager that handles rooms & users
from signaling import manager

# Create a router for websocket endpoints
router = APIRouter(
    prefix="/ws",          # All websocket URLs will start with /ws
    tags=["signaling"]     # Group name shown in docs
)

# WebSocket endpoint for a specific meeting room
@router.websocket("/{room_id}")
async def websocket_signaling(websocket: WebSocket, room_id: str):

    # Connect the user to the room and get a temporary peer ID
    temp_peer_id = await manager.connect(room_id, websocket)
    stable_peer_id = temp_peer_id # we'll update this once 'join' is received

    try:
        # Keep listening for messages forever while connected
        while True:

            # Receive message from frontend in JSON format
            data = await websocket.receive_json()
            
            # Add sender ID so others know who sent the message
            data["sender_id"] = stable_peer_id
            
            # ========== WHEN USER JOINS ==========
            if data.get("type") == "join":
                username = data.get("username", "Guest")
                role = data.get("role", "student")
                user_id = data.get("userId") or temp_peer_id # Use stable ID from frontend if provided
                
                # Update our tracking ID to the stable one
                stable_peer_id = user_id
                data["sender_id"] = stable_peer_id

                # CHECK IF ALREADY APPROVED (Seamless Re-join)
                # If they were already in 'peers', they don't need to wait again
                is_already_approved = room_id in manager.rooms and user_id in manager.rooms[room_id]["approved_users"]
                
                # IF ADMIN -> Join normally
                if role == "admin":
                    await manager.add_to_peers(room_id, user_id, websocket, username, role)
                    
                    # Get updated participant list & presenter
                    users, presenter = manager.get_participants(room_id)

                    # Send updated participants list to everyone approved
                    await manager.broadcast(room_id, {
                        "type": "participants",
                        "users": users,
                        "presenter": presenter
                    })

                    # Tell other approved peers someone joined
                    await manager.broadcast(room_id, {
                        "type": "join",
                        "sender_id": user_id,
                        "username": username
                    }, sender_id=user_id)

                    history = manager.get_messages(room_id)
                    if history:
                        await websocket.send_json({
                            "type": "chat-history",
                            "history": history
                        })
                    
                    # Send the current waiting room list
                    waiting_users = manager.get_waiting_users(room_id)
                    if waiting_users:
                        await websocket.send_json({
                            "type": "waiting-users-list",
                            "users": waiting_users
                        })

                # IF STUDENT (PREVIOUSLY APPROVED) -> Seamless Re-join flow
                elif is_already_approved:
                    print(f"User {user_id} re-joining approved room {room_id}. Sending join-approved.")
                    await websocket.send_json({
                        "type": "join-approved"
                    })

                # IF NEW STUDENT -> Move to Waiting Room
                else:
                    await manager.move_to_waiting(room_id, user_id, websocket, username, role)
                    
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
                username = data.get("username", "Guest")
                role = data.get("role", "student")
                user_id = stable_peer_id

                # Finalize the transition to 'peers'
                # (Removing from waiting list if they were there)
                manager.disconnect(room_id, user_id, websocket) 
                await manager.add_to_peers(room_id, user_id, websocket, username, role)
                
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
                continue

            # ========== ADMIN APPROVE USER ==========
            if data.get("type") == "approve-user":
                sender_info = manager.rooms.get(room_id, {}).get("peers", {}).get(stable_peer_id, {})
                if sender_info.get("role") == "admin":
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
                if sender_info.get("role") == "admin":
                    target_id = data.get("targetUserId")
                    await manager.kick_user(room_id, target_id)
                continue

            # ========== SCREEN SHARE EVENT ==========
            if data.get("type") == "screen-share":

                # If user started sharing screen
                if data.get("isSharing"):
                    manager.set_presenter(room_id, stable_peer_id)

                # If user stopped sharing
                else:
                    users, presenter = manager.get_participants(room_id)

                    # Remove presenter if this user was presenting
                    if presenter == stable_peer_id:
                        manager.set_presenter(room_id, None)

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

                # Only admin can kick users
                if sender_info.get("role") == "admin":

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