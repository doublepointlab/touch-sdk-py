import asyncio
from bleak import BleakClient, BleakScanner
import mido
import os

# MIDI BLE UUIDs
MIDI_SERVICE_UUID = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
MIDI_CHARACTERISTIC_UUID = "7772e5db-3868-4112-a1a9-f2669d106bf3"

# Default MIDI note and velocity
DEFAULT_NOTE = 60
VELOCITY = 100
CHANNEL = 0  # Channel 1 (0-indexed)

# File to store the last selected device information
DEVICE_FILE = "last_selected_device.txt"

# Convert MIDI message to bytes
def midi_to_bytes(message):
    print(f"Sending MIDI message: {message}")  # Debugging: print the message being sent
    return bytes(message.bytes())

# Save selected device information to a file
def save_device_info(device):
    with open(DEVICE_FILE, 'w') as f:
        f.write(f"{device.name}\n{device.address}")

# Load the last saved device information
def load_device_info():
    if os.path.exists(DEVICE_FILE):
        with open(DEVICE_FILE, 'r') as f:
            lines = f.readlines()
            if len(lines) == 2:
                name = lines[0].strip()
                address = lines[1].strip()
                return name, address
    return None, None

# Scan for BLE devices and sort by name
async def scan_ble_devices():
    devices = await BleakScanner.discover()
    # Filter devices with names and sort alphabetically by name
    named_devices = sorted(
        [device for device in devices if device.name], 
        key=lambda d: d.name
    )
    for i, device in enumerate(named_devices):
        print(f"{i}: Device: {device.name}, Address: {device.address}")
    return named_devices

# Keep the BLE connection open and send MIDI messages
async def keep_connection_open(client):
    print("Connection is now open. Hit 'Enter' to send a MIDI message for 1 second or type 'exit' to disconnect.")
    try:
        while True:
            command = input("Enter MIDI note number (default 60) or type 'exit' to disconnect: ").strip().lower()
            if command == '':
                note = DEFAULT_NOTE
            elif command == 'exit':
                print("Disconnecting...")
                break
            else:
                try:
                    note = int(command)
                except ValueError:
                    print("Invalid input. Please enter a valid MIDI note number or 'exit'.")
                    continue

            # Send Note On
            note_on = mido.Message('note_on', channel=CHANNEL, note=note, velocity=VELOCITY)
            await client.write_gatt_char(MIDI_CHARACTERISTIC_UUID, midi_to_bytes(note_on))
            print(f"Note On sent for channel 1, note {note}, velocity {VELOCITY}. Holding for 1 second...")

            # Wait for 1 second
            await asyncio.sleep(1)

            # Send Note Off
            note_off = mido.Message('note_off', channel=CHANNEL, note=note, velocity=VELOCITY)
            await client.write_gatt_char(MIDI_CHARACTERISTIC_UUID, midi_to_bytes(note_off))
            print("Note Off sent.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await client.disconnect()
        print("Disconnected.")

# Function to handle USB MIDI device
def handle_usb_midi_device():
    output_names = mido.get_output_names()
    if output_names:
        print("USB MIDI device detected:", output_names[0])
        with mido.open_output(output_names[0]) as output:
            while True:
                command = input("Enter MIDI note number (default 60) or type 'exit' to disconnect: ").strip().lower()
                if command == '':
                    note = DEFAULT_NOTE
                elif command == 'exit':
                    print("Exiting...")
                    break
                else:
                    try:
                        note = int(command)
                    except ValueError:
                        print("Invalid input. Please enter a valid MIDI note number or 'exit'.")
                        continue

                # Send Note On
                note_on = mido.Message('note_on', channel=CHANNEL, note=note, velocity=VELOCITY)
                output.send(note_on)
                print(f"Note On sent for channel 1, note {note}, velocity {VELOCITY}. Holding for 1 second...")

                # Wait for 1 second
                asyncio.sleep(1)

                # Send Note Off
                note_off = mido.Message('note_off', channel=CHANNEL, note=note, velocity=VELOCITY)
                output.send(note_off)
                print("Note Off sent.")

# Main function to load, scan, and maintain connection
async def main():
    # Check if there are any USB MIDI devices connected
    output_names = mido.get_output_names()
    if output_names:
        handle_usb_midi_device()
    else:
        while True:
            # Try to load the last remembered device
            last_name, last_address = load_device_info()

            if last_name and last_address:
                print(f"Last used device found: {last_name} ({last_address})")
                print("Press 'Enter' to connect to the remembered device, or 'r' to rescan for devices.")
                user_input = input("Your choice: ").strip().lower()

                if user_input == '':  # Connect to the remembered device
                    client = BleakClient(last_address)
                    await client.connect()
                    if client.is_connected:
                        print(f"Connected to {last_address}")
                        await keep_connection_open(client)
                    return
                elif user_input == 'r':  # Rescan for devices
                    print("Rescanning for devices...")
                else:
                    print("Invalid input. Please try again.")
                    continue

            # If no remembered device or user chooses to rescan, scan for devices
            devices = await scan_ble_devices()

            if not devices:
                print("No BLE devices found.")
                return

            # Prompt the user to select a device by index
            print("Press 'Enter' without typing anything to rescan for devices.")
            device_index_input = input("Select device by index: ").strip()

            # If the user hits Enter without typing anything, rescan
            if device_index_input == '':
                continue

            # Ensure the input is a valid index
            try:
                device_index = int(device_index_input)
                selected_device = devices[device_index]
            except (ValueError, IndexError):
                print("Invalid index. Please try again.")
                continue

            print(f"Selected Device: {selected_device.name}, Address: {selected_device.address}")

            # Save the selected device information for future use
            save_device_info(selected_device)

            # Connect and keep the connection open
            client = BleakClient(selected_device.address)
            await client.connect()
            if client.is_connected:
                print(f"Connected to {selected_device.address}")
                await keep_connection_open(client)
            return

if __name__ == "__main__":
    asyncio.run(main())