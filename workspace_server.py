import socket
import threading
import time
from workspace_users import workspace_users

class WorkspaceServer:
    def __init__(self, host='0.0.0.0', port=5556):
        self.host = host
        self.port = port
        self.clients = []
        self.lock = threading.Lock()
        self.users = {}
        self.sockets = {}
        self.activity = {}
        self.projects = {}
        self.notifications = []
        # file access permissions
        self.file_permissions = {
            "pic.png": ["Ahmed", "Matthew"],
            "file.xlsx": ["Ahmed"],
            "test.txt": ["Ahmed", "Matthew", "John"],
            "design.png": ["Ahmed", "Matthew"],
            "mockup.pdf": ["Ahmed", "Matthew"]
        }
        
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self.host, self.port))
        sock.listen(5)
        print(f"workspace server running on {self.host}:{self.port}")
        
        # start background thread to check if clients are still connected
        threading.Thread(target=self.check_activity, daemon=True).start()
        
        while True:
            client, addr = sock.accept()
            print(f"connection from {addr}")
            threading.Thread(target=self.handle_client, args=(client,)).start()
    # Handle client communication
    def handle_client(self, client):
        username = self.login(client)
        if not username:
            client.close()
            return
            
        with self.lock:
            self.clients.append(client)
            self.users[client] = username
            self.sockets[username] = client
            self.activity[client] = time.time()
        
        role = workspace_users.get(username, {}).get('role', 'viewers')
        client.send(f"role: {role}\n".encode())
        
        try:
            while True:
                data = client.recv(4096)
                if not data:
                    break
                    
                msg = data.decode().strip()
                
                if msg.lower() in ['hi', 'here', 'hello']:
                    with self.lock:
                        self.activity[client] = time.time()
                    client.send("ok\n".encode())
                    continue
                
                if msg == 'who':
                    self.show_online(client)
                elif msg.startswith('@'):
                    self.send_private(client, username, msg)
                elif msg.startswith('/project'):
                    self.handle_project(client, username, msg)
                elif msg == 'logout':
                    break
                else:
                    client.send("try: who, @user msg, /project help, logout\n".encode())
                
                with self.lock:
                    self.activity[client] = time.time()
                    
        except:
            pass
        finally:
            self.remove_client(client)
    # Login method
    def login(self, client):
        try:
            data = client.recv(1024).decode().strip()
            if not data.startswith('login:'):
                client.send(b'FAIL\n')
                return None
                
            parts = data.split(':', 2)
            if len(parts) < 3:
                client.send(b'FAIL\n') 
                return None
                
            username = parts[1]
            password = parts[2]
            
            user = workspace_users.get(username) 
            if user and user['password'] == password:
                user['online'] = True
                client.send(b'OK\n')
                print(f"{username} logged in")
                return username
            else:
                client.send(b'FAIL\n')
                return None
        except:
            client.send(b'FAIL\n')
            return None
    # Show online users
    def show_online(self, client):
        online = []
        for u, data in workspace_users.items():  
            if data.get('online'):
                online.append(u)
        
        if online:
            msg = f"online: {', '.join(online)}"
        else:
            msg = "nobody online"
        client.send(msg.encode())
    
    def send_private(self, client, sender, msg):
        try:
            parts = msg.split(' ', 1)
            target = parts[0][1:]
            message = parts[1]
            
            with self.lock:
                target_sock = self.sockets.get(target)
            
            if target_sock and target_sock in self.clients:
                target_sock.send(f"[{sender}]: {message}".encode())
                client.send(f"-> {target}: {message}".encode())
            else:
                client.send(f"{target} not online".encode())
        except:
            client.send("usage: @username message".encode())
    # This method handles all /project commands
    def handle_project(self, client, username, msg):
        parts = msg.split()
        if len(parts) < 2:
            self.help_project(client)
            return
        
        cmd = parts[1]
        role = workspace_users.get(username, {}).get('role', 'viewers')
        
        if cmd == 'help':
            self.help_project(client)
        elif cmd == 'create' and len(parts) >= 3:
            if role != 'admin':
                client.send("need admin role".encode())
                return
            project_name = parts[2]
            if project_name not in self.projects:
                # add some files to new projects
                files = ["design.png", "mockup.pdf"] if "website" in project_name else []
                self.projects[project_name] = {
                    "creator": username,
                    "members": [username],
                    "active": True,
                    "created_date": "2025-10-30",
                    "files": files
                }
                client.send(f"created {project_name}".encode())
            else:
                client.send(f"{project_name} exists".encode())
        elif cmd == 'join' and len(parts) >= 3:
            project_name = parts[2]
            if project_name in self.projects:
                if username not in self.projects[project_name]["members"]:
                    self.projects[project_name]["members"].append(username)
                    client.send(f"joined {project_name}".encode())
                else:
                    client.send(f"already in {project_name}".encode())
            else:
                client.send(f"{project_name} not found".encode())
        elif cmd == 'add' and len(parts) >= 4:
            if role not in ['admin', 'editor']:
                client.send("need admin or editor".encode())
                return
            project_name = parts[2]
            target_user = parts[3]
            if project_name not in self.projects:
                client.send(f"{project_name} not found".encode())
                return
            if target_user not in workspace_users:
                client.send(f"user {target_user} not found".encode())
                return
            if target_user not in self.projects[project_name]["members"]:
                self.projects[project_name]["members"].append(target_user)
                client.send(f"added {target_user} to {project_name}".encode())
                
                # add notification
                notification = {
                    "user": target_user,
                    "message": f"Added to {project_name} project",
                    "timestamp": time.strftime("%H:%M")
                }
                self.notifications.append(notification)
                
                # notify the added user if they're online
                with self.lock:
                    target_sock = self.sockets.get(target_user)
                if target_sock and target_sock in self.clients:
                    target_sock.send(f"[NOTIFICATION] Added to {project_name} project by {username}".encode())
            else:
                client.send(f"{target_user} already in {project_name}".encode())
        elif cmd == 'kick' and len(parts) >= 4:
            if role not in ['admin', 'editor']:
                client.send("need admin or editor".encode())
                return
            project_name = parts[2]
            target_user = parts[3]
            if project_name in self.projects and target_user in self.projects[project_name]["members"]:
                self.projects[project_name]["members"].remove(target_user)
                client.send(f"kicked {target_user} from {project_name}".encode())
            else:
                client.send("project or user not found".encode())
        elif cmd == 'leave' and len(parts) >= 3:
            if role not in ['admin', 'editor']:
                client.send("need admin or editor".encode())
                return
            project_name = parts[2]
            if project_name in self.projects and username in self.projects[project_name]["members"]:
                self.projects[project_name]["members"].remove(username)
                client.send(f"left {project_name}".encode())
            else:
                client.send("not in that project".encode())
        elif cmd == 'list':
            if self.projects:
                project_list = []
                for name, project_data in self.projects.items():
                    member_count = len(project_data["members"])
                    creator = project_data["creator"]
                    active_status = "active" if project_data["active"] else "inactive"
                    project_list.append(f"{name}({member_count}) by {creator} [{active_status}]")
                client.send(f"projects: {', '.join(project_list)}".encode())
            else:
                client.send("no projects".encode())
        elif cmd == 'message' and len(parts) >= 4:
            project_name = parts[2]
            message = ' '.join(parts[3:])
            if project_name in self.projects and username in self.projects[project_name]["members"]:
                # send message to all project members
                for member in self.projects[project_name]["members"]:
                    with self.lock:
                        member_sock = self.sockets.get(member)
                    if member_sock and member_sock in self.clients and member != username:
                        member_sock.send(f"[{project_name}] {username}: {message}".encode())
                client.send(f"sent to {project_name}: {message}".encode())
            else:
                client.send(f"not in project {project_name}".encode())
        elif cmd == 'info' and len(parts) >= 3:
            project_name = parts[2]
            if project_name in self.projects:
                p = self.projects[project_name]
                info = f"Project: {project_name}\nCreator: {p['creator']}\nMembers: {', '.join(p['members'])}\nFiles: {', '.join(p['files'])}"
                client.send(info.encode())
            else:
                client.send("project not found".encode())
        elif cmd == 'files' and len(parts) >= 3:
            project_name = parts[2]
            if project_name in self.projects:
                files = self.projects[project_name]["files"]
                result = []
                for f in files:
                    # check if user has permission to access this file
                    can_access = username in self.file_permissions.get(f, [])
                    status = "can access" if can_access else "no access"
                    result.append(f"{f} - {status}")
                if result:
                    client.send("\n".join(result).encode())
                else:
                    client.send("no files".encode())
            else:
                client.send("project not found".encode())
        elif cmd == 'upload' and len(parts) >= 4:
            project_name = parts[2]
            filename = parts[3]
            if project_name in self.projects:
                if username in self.projects[project_name]["members"]:
                    if filename not in self.projects[project_name]["files"]:
                        self.projects[project_name]["files"].append(filename)
                        # give uploader access to their file
                        if filename not in self.file_permissions:
                            self.file_permissions[filename] = [username]
                        client.send(f"uploaded {filename} to {project_name}".encode())
                        
                        # add file upload notification
                        notification = {
                            "user": username,
                            "message": f"New file uploaded to {project_name}",
                            "timestamp": time.strftime("%H:%M")
                        }
                        self.notifications.append(notification)
                    else:
                        client.send("file already exists".encode())
                else:
                    client.send("not in project".encode())
            else:
                client.send("project not found".encode())
        elif cmd == 'notifications':
            if self.notifications:
                result = []
                for notif in self.notifications:
                    result.append(f"{notif['user']}: {notif['message']} at {notif['timestamp']}")
                client.send("\n".join(result).encode())
            else:
                client.send("no notifications".encode())
        else:
            client.send("unknown command".encode())
    
    def help_project(self, client):
        help_text = """project commands:
/project create name - make project (admin only)
/project join name - join project
/project add name user - add user to project (admin/editor)
/project kick name user - kick user (admin/editor)
/project leave name - leave project (admin/editor)  
/project list - show projects
/project info name - show project details
/project files name - show project files
/project upload name filename - add file to project
/project notifications - show recent notifications
/project message name text - send message to project"""
        client.send(help_text.encode())
    
    def check_activity(self):
        while True:
            time.sleep(15)
            now = time.time()
            
            with self.lock:
                check_clients = self.clients.copy()
            
            for client in check_clients:
                try:
                    last_seen = self.activity.get(client, 0)
                    
                    if now - last_seen > 30:
                        username = self.users.get(client, "unknown")
                        client.send(b"still there? say 'hi' in 30 seconds")
                        
                        time.sleep(30)
                        if now - self.activity.get(client, 0) > 60:
                            print(f"disconnecting {username}")
                            self.remove_client(client)
                except:
                    self.remove_client(client)
    
    def remove_client(self, client):
        try:
            username = self.users.get(client, "unknown")
            
            with self.lock:
                if client in self.clients:
                    self.clients.remove(client)
                self.users.pop(client, None)
                self.activity.pop(client, None)
                if username != "unknown":
                    self.sockets.pop(username, None)
                    if username in workspace_users:
                        workspace_users[username]['online'] = False
            
            client.close()
            print(f"{username} disconnected")
            
        except Exception as e:
            print(f"error removing client: {e}")

if __name__ == '__main__':
    print("starting workspace server...")
    server = WorkspaceServer()
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nstopped")