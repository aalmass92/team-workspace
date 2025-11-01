import socket
import threading
import os

def listen(sock):
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                print("disconnected")
                break

            msg = data.decode()
            print(f"\n{msg}")
        except:
            print("lost connection")
            break

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    ip = input("workspace server ip: ")
    try:
        sock.connect((ip, 5556))
    except:
        print("connection failed")
        return

    user = input("username: ")
    pwd = input("password: ")
    sock.send(f"login:{user}:{pwd}".encode())
    
    resp = sock.recv(1024).decode().strip()
    if resp != "OK":
        print(f"login failed: {resp}")
        sock.close()
        return
    
    print("connected to workspace")
    
    threading.Thread(target=listen, args=(sock,), daemon=True).start()

    print("commands: @user msg, who, /project help, logout")
    
    while True:
        msg = input()
        
        if msg == 'logout':
            sock.send(b"logout")
            break
        elif msg in ['hi', 'here', 'hello']:
            print("staying connected")
        elif msg == 'help':
            print("@user msg, who, /project help, logout")
            continue
            
        try:
            sock.send(msg.encode())
        except:
            print("send failed")
            break
    
    sock.close()

if __name__ == "__main__":
    main()