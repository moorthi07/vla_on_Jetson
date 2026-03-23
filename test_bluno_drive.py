import serial, time, subprocess

def connect():
    subprocess.run(["sudo", "rfcomm", "release", "0"], capture_output=True)
    time.sleep(0.5)
    subprocess.run(["sudo", "rfcomm", "bind", "0", "C8:A0:30:F9:5E:EC", "1"], capture_output=True)
    time.sleep(1)
    ser = serial.Serial("/dev/rfcomm0", 9600, timeout=2)
    time.sleep(0.5)  # wait for connection to stabilize
    return ser

ser = connect()
print("Connected!")

for cmd in ["f", "s", "b", "s", "l", "s", "r", "s"]:
    try:
        ser.write(f"{cmd}\n".encode())
        print(f"Sent: {cmd}")
        # Read any response
        time.sleep(0.2)
        if ser.in_waiting:
            print(f"Response: {ser.read(ser.in_waiting).decode('utf-8', errors='ignore')}")
        time.sleep(1.5)
    except Exception as e:
        print(f"Error: {e}, reconnecting...")
        ser = connect()

ser.close()
