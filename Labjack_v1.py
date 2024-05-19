import asyncio
from datetime import datetime, timedelta
import tkinter as tk
from labjack import ljm
import threading
import queue

class ValveInputDialog:
    def __init__(self, root, message_queue):
        self.root = root
        self.root.geometry("800x600")
        self.root.title("Valve Configuration")

        self.message_queue = message_queue

        self.num_valves_label = tk.Label(root, text="Number of Valves:")
        self.num_valves_label.pack()
        self.num_valves_entry = tk.Entry(root)
        self.num_valves_entry.pack()

        self.submit_button = tk.Button(root, text="Submit", command=self.create_valve_entries)
        self.submit_button.pack()

        self.valve_configs_frame = tk.Frame(self.root)
        self.valve_configs_frame.pack()

        self.start_button = tk.Button(self.root, text="Start", command=self.open_monitoring_window)
        self.start_button.pack()
        self.start_button.pack_forget()  # Hide the start button initially

        self.valve_entries = []
        self.valve_counters = []
        self.valve_states = []
        self.valve_configs = []

    def create_valve_entries(self):
        num_valves = int(self.num_valves_entry.get())
        self.valve_entries = []
        self.valve_counters = []
        self.valve_states = []
        for i in range(num_valves):
            frame = tk.Frame(self.valve_configs_frame)
            frame.pack()

            label = tk.Label(frame, text=f"Valve {i}")
            label.grid(row=0, column=0)

            off_time_label = tk.Label(frame, text="OFF time (seconds):")
            off_time_label.grid(row=0, column=1)
            off_time_entry = tk.Entry(frame)
            off_time_entry.grid(row=0, column=2)

            on_time_label = tk.Label(frame, text="ON time (seconds):")
            on_time_label.grid(row=0, column=3)
            on_time_entry = tk.Entry(frame)
            on_time_entry.grid(row=0, column=4)

            counter_label = tk.Label(frame, text="Cycles: 0")
            counter_label.grid(row=0, column=5)

            state_label = tk.Label(frame, text="OFF", fg="red")
            state_label.grid(row=0, column=6)

            self.valve_entries.append((off_time_entry, on_time_entry))
            self.valve_counters.append(counter_label)
            self.valve_states.append(state_label)

        self.start_button.pack()  # Show the start button after creating entries

    def start_valves(self):
        self.valve_configs = [(int(off_entry.get()), int(on_entry.get())) for off_entry, on_entry in self.valve_entries]
        self.root.quit()

    def open_monitoring_window(self):
        self.start_valves()
        self.root.destroy()

class MonitoringWindow:
    def __init__(self, root, message_queue, valve_configs):
        self.root = root
        self.root.geometry("800x600")
        self.root.title("Valve Monitoring")

        self.message_queue = message_queue
        self.valve_counters = []
        self.valve_states = []
        self.valve_configs = valve_configs

        for i, (off_time, on_time) in enumerate(valve_configs):
            frame = tk.Frame(self.root)
            frame.pack()

            label = tk.Label(frame, text=f"Valve {i}")
            label.grid(row=0, column=0)

            off_time_label = tk.Label(frame, text=f"OFF time (seconds): {off_time}")
            off_time_label.grid(row=0, column=1)

            on_time_label = tk.Label(frame, text=f"ON time (seconds): {on_time}")
            on_time_label.grid(row=0, column=2)

            counter_label = tk.Label(frame, text="Cycles: 0")
            counter_label.grid(row=0, column=3)
            self.valve_counters.append(counter_label)

            state_label = tk.Label(frame, text="OFF", fg="red")
            state_label.grid(row=0, column=4)
            self.valve_states.append(state_label)

        self.status_label = tk.Label(self.root, text="", fg="blue", font=("Helvetica", 12), width=50)
        self.status_label.pack()

        stop_button = tk.Button(self.root, text="Stop", command=self.stop_valves)
        stop_button.pack()

    def stop_valves(self):
        global running
        running = False
        self.status_label.config(text="Finalizing and closing the valves")
        self.root.update_idletasks()  # Force GUI to update immediately
        for i in range(len(self.valve_configs)):
            ljm.eWriteName(handle, name[i], 0)
        # Confirming all valves are set to 0
        states = ljm.eReadNames(handle, len(name), name)
        self.status_label.config(text="All valves set to OFF")
        self.root.update_idletasks()  # Force GUI to update immediately
        self.root.quit()

    def process_messages(self):
        while not self.message_queue.empty():
            msg = self.message_queue.get_nowait()
            if msg["type"] == "update":
                valve_index = msg["valve"]
                cycles = msg["cycles"]
                state = msg["state"]

                state_text = "ON" if state else "OFF"
                state_color = "green" if state else "red"

                self.valve_counters[valve_index].config(text=f"Cycles: {cycles}")
                self.valve_states[valve_index].config(text=state_text, fg=state_color)

        self.root.after(100, self.process_messages)  # Check the queue every 100 ms

def append_new_line(file_name, text_to_append):
    with open(file_name, "a+") as file_object:
        file_object.seek(0)
        data = file_object.read(100)
        if len(data) > 0:
            file_object.write("\n")
        file_object.write("\t".join(map(str, text_to_append)))

async def state_update(V, ON, OFF, message_queue):
    c = 0
    while running:
        # Start with OFF state
        State[V] = 0
        ljm.eWriteName(handle, name[V], State[V])
        print(f"Valve {V} set to OFF (State: {State[V]})")  # Debug print

        message_queue.put({"type": "update", "valve": V, "cycles": c, "state": 0})

        off_end_time = datetime.now() + timedelta(seconds=OFF)
        while datetime.now() < off_end_time:
            if not running:
                return
            await asyncio.sleep(0.1)

        # Set valve to ON
        State[V] = 1
        ljm.eWriteName(handle, name[V], State[V])
        print(f"Valve {V} set to ON (State: {State[V]})")  # Debug print

        message_queue.put({"type": "update", "valve": V, "cycles": c, "state": 1})

        on_end_time = datetime.now() + timedelta(seconds=ON)
        while datetime.now() < on_end_time:
            if not running:
                return
            await asyncio.sleep(0.1)

        # Increment cycle counter
        c += 1
        message_queue.put({"type": "update", "valve": V, "cycles": c, "state": State[V]})

async def Reader(Freq):
    t0 = datetime.now()
    while running:
        t1 = datetime.now()
        t2 = t1 - t0
        t1s = t1.strftime("%Y-%m-%d %H:%M:%S.%f")
        t2s = t2.seconds
        results = ljm.eReadAddress(handle, 2501, 0)
        results_08b = format(int(results), '08b')
        results_digit = [int(x) for x in results_08b][::-1]
        results_time = results_digit + [str(t2s), t1s]
        append_new_line(filename, results_time)
        print(results_time)
        await asyncio.sleep(Freq)
        if not running:
            break

async def main():
    global t0, filename, name, State, handle, running
    t0 = datetime.now()
    filename = "Valve_data_" + t0.strftime("%Y_%m_%d-%I_%M_%S") + ".txt"
    headers = 'V0 V1 V2 V3 V4 V5 V6 V7 Elapsed DateTime'.split()

    with open(filename, "a") as f:
        append_new_line(filename, headers)

    tasks = [Reader(1)]
    for i, (off_time, on_time) in enumerate(valve_configs):
        print(f"Starting valve {i} with OFF time: {off_time}, ON time: {on_time}")  # Debug print
        tasks.append(state_update(i, on_time, off_time, message_queue))

    await asyncio.gather(*tasks)

def run_asyncio_loop():
    asyncio.run(main())

if __name__ == "__main__":
    message_queue = queue.Queue()
    running = True

    root = tk.Tk()
    app = ValveInputDialog(root, message_queue)
    root.mainloop()

    valve_configs = app.valve_configs
    valve_counters = app.valve_counters
    valve_states = app.valve_states

    num_valves = len(valve_configs)
    name = [f"EIO{i}" for i in range(num_valves)]
    handle = ljm.openS("T7", "USB", "ANY")
    State = [0] * num_valves
    ljm.eWriteNames(handle, len(name), name, State)

    # Ensure no extra valves are ON
    extra_valves = [f"EIO{i}" for i in range(num_valves, 8)]
    ljm.eWriteNames(handle, len(extra_valves), extra_valves, [0] * len(extra_valves))

    # Open the monitoring window
    monitoring_root = tk.Tk()
    monitoring_window = MonitoringWindow(monitoring_root, message_queue, valve_configs)
    monitoring_root.after(100, monitoring_window.process_messages)  # Start processing the queue

    # Start the asyncio event loop in a separate thread
    asyncio_thread = threading.Thread(target=run_asyncio_loop)
    asyncio_thread.start()

    monitoring_root.mainloop()

    # Stop the asyncio event loop after closing the monitoring window
    running = False
    asyncio_thread.join()
    # Ensure all valves are set to OFF
    for i in range(num_valves):
        ljm.eWriteName(handle, name[i], 0)
    states = ljm.eReadNames(handle, len(name), name)
    print("All valves set to OFF after stopping:", states)