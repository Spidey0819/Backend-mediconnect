from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
import uuid
from datetime import datetime

# Store room information
rooms = {}

def init_webrtc_signaling(app):
    """Initialize WebRTC signaling with Socket.IO"""
    
    # Initialize SocketIO with CORS settings
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        async_mode='threading',
        logger=False,
        engineio_logger=False
    )
    
    @socketio.on('connect')
    def handle_connect():
        print(f'Client connected: {request.sid}')
        emit('connected', {
            'status': 'Connected to WebRTC signaling server',
            'clientId': request.sid,
            'timestamp': datetime.now().isoformat()
        })

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'Client disconnected: {request.sid}')
        
        # Remove user from all rooms
        for room_id, room_data in list(rooms.items()):
            if request.sid in room_data['users']:
                # Get user data before removing
                user_data = room_data['users'][request.sid]
                del room_data['users'][request.sid]
                
                print(f'Removed {user_data["name"]} from room {room_id}')
                
                # Notify others in room
                socketio.emit('user-left', {
                    'user': user_data,
                    'users': list(room_data['users'].values()),
                    'timestamp': datetime.now().isoformat()
                }, room=room_id)
                
                # Clean up empty rooms
                if len(room_data['users']) == 0:
                    print(f'Cleaning up empty room: {room_id}')
                    del rooms[room_id]

    @socketio.on('join-room')
    def handle_join_room(data):
        try:
            room_id = data['roomId']
            user_role = data['userRole']
            user_name = data['userName']
            
            print(f'Join room request: {user_name} ({user_role}) -> {room_id}')
            
            # Join the room
            join_room(room_id)
            
            # Initialize room if doesn't exist
            if room_id not in rooms:
                rooms[room_id] = {
                    'users': {},
                    'created_at': datetime.now().isoformat(),
                    'room_id': room_id
                }
                print(f'Created new room: {room_id}')
            
            # Add user to room
            user_data = {
                'id': request.sid,
                'role': user_role,
                'name': user_name,
                'joined_at': datetime.now().isoformat()
            }
            
            rooms[room_id]['users'][request.sid] = user_data
            
            print(f'User {user_name} ({user_role}) joined room {room_id}. Total users: {len(rooms[room_id]["users"])}')
            
            # Notify user they joined successfully
            emit('joined-room', {
                'roomId': room_id,
                'user': user_data,
                'users': list(rooms[room_id]['users'].values()),
                'timestamp': datetime.now().isoformat()
            })
            
            # Notify others in room about new user
            emit('user-joined', {
                'user': user_data,
                'users': list(rooms[room_id]['users'].values()),
                'timestamp': datetime.now().isoformat()
            }, room=room_id, include_self=False)
            
        except Exception as e:
            print(f'Error in join-room: {e}')
            emit('error', {'message': f'Failed to join room: {str(e)}'})

    @socketio.on('offer')
    def handle_offer(data):
        try:
            room_id = data['roomId']
            offer = data['offer']
            
            print(f'Relaying offer in room {room_id} from {request.sid}')
            
            # Validate room exists
            if room_id not in rooms:
                emit('error', {'message': 'Room not found'})
                return
            
            # Send offer to all other users in room
            emit('offer', {
                'offer': offer,
                'from': request.sid,
                'timestamp': datetime.now().isoformat()
            }, room=room_id, include_self=False)
            
            print(f'Offer relayed successfully in room {room_id}')
            
        except Exception as e:
            print(f'Error in offer: {e}')
            emit('error', {'message': f'Failed to send offer: {str(e)}'})

    @socketio.on('answer')
    def handle_answer(data):
        try:
            room_id = data['roomId']
            answer = data['answer']
            
            print(f'Relaying answer in room {room_id} from {request.sid}')
            
            # Validate room exists
            if room_id not in rooms:
                emit('error', {'message': 'Room not found'})
                return
            
            # Send answer to all other users in room
            emit('answer', {
                'answer': answer,
                'from': request.sid,
                'timestamp': datetime.now().isoformat()
            }, room=room_id, include_self=False)
            
            print(f'Answer relayed successfully in room {room_id}')
            
        except Exception as e:
            print(f'Error in answer: {e}')
            emit('error', {'message': f'Failed to send answer: {str(e)}'})

    @socketio.on('ice-candidate')
    def handle_ice_candidate(data):
        try:
            room_id = data['roomId']
            candidate = data['candidate']
            
            print(f'Relaying ICE candidate in room {room_id} from {request.sid}')
            
            # Validate room exists
            if room_id not in rooms:
                emit('error', {'message': 'Room not found'})
                return
            
            # Send ICE candidate to all other users in room
            emit('ice-candidate', {
                'candidate': candidate,
                'from': request.sid,
                'timestamp': datetime.now().isoformat()
            }, room=room_id, include_self=False)
            
        except Exception as e:
            print(f'Error in ice-candidate: {e}')
            emit('error', {'message': f'Failed to send ICE candidate: {str(e)}'})

    @socketio.on('leave-room')
    def handle_leave_room(data):
        try:
            room_id = data['roomId']
            
            if room_id in rooms and request.sid in rooms[room_id]['users']:
                # Get user data before removing
                user_data = rooms[room_id]['users'][request.sid]
                
                # Remove user from room
                del rooms[room_id]['users'][request.sid]
                leave_room(room_id)
                
                print(f'User {user_data["name"]} left room {room_id}')
                
                # Notify others in room
                emit('user-left', {
                    'user': user_data,
                    'users': list(rooms[room_id]['users'].values()),
                    'timestamp': datetime.now().isoformat()
                }, room=room_id)
                
                # Clean up empty rooms
                if len(rooms[room_id]['users']) == 0:
                    print(f'Cleaning up empty room: {room_id}')
                    del rooms[room_id]
                    
        except Exception as e:
            print(f'Error in leave-room: {e}')
            emit('error', {'message': f'Failed to leave room: {str(e)}'})

    @socketio.on('get-room-info')
    def handle_get_room_info(data):
        try:
            room_id = data['roomId']
            
            if room_id in rooms:
                emit('room-info', {
                    'roomId': room_id,
                    'users': list(rooms[room_id]['users'].values()),
                    'created_at': rooms[room_id]['created_at'],
                    'timestamp': datetime.now().isoformat()
                })
            else:
                emit('room-info', {
                    'roomId': room_id,
                    'users': [],
                    'message': 'Room not found',
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f'Error in get-room-info: {e}')
            emit('error', {'message': f'Failed to get room info: {str(e)}'})

    # Global error handling
    @socketio.on_error_default
    def default_error_handler(e):
        print(f'SocketIO error: {e}')
        emit('error', {
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        })

    # Additional events
    @socketio.on('ping')
    def handle_ping():
        emit('pong', {
            'timestamp': datetime.now().isoformat(),
            'client_id': request.sid
        })

    print("WebRTC signaling server initialized successfully")
    return socketio

def get_active_rooms():
    """Get information about active rooms"""
    return {
        'total_rooms': len(rooms),
        'rooms': {
            room_id: {
                'user_count': len(room_data['users']),
                'users': [user['name'] + ' (' + user['role'] + ')' for user in room_data['users'].values()],
                'created_at': room_data['created_at']
            }
            for room_id, room_data in rooms.items()
        }
    }