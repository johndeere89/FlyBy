import tkinter as tk
from PIL import Image, ImageTk
import threading
import queue
import requests
import time
import os
import logging
import csv
from datetime import datetime
from pathlib import Path

# === Basis configuratie en paden ===
SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE_FILE = SCRIPT_DIR / "clouds.png"
LOGO_DIR = SCRIPT_DIR / "logos"
PING_FILE = SCRIPT_DIR / "ping.mp3"
LOG_FILE = SCRIPT_DIR / "vliegtuigmonitor.log"

# === Configuratie scherm ===
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 450
SCROLL_SPEED = 0.1
FRAME_DELAY = 4

# === Configuratie vlieggebied ===
MIN_LAT = 52.64667
MAX_LAT = 52.74778
MIN_LON = 5.02139
MAX_LON = 5.30444

# === API instellingen ===
AIRCRAFT_URL = "http://localhost:8080/data/aircraft.json"
AEROAPI_TOKEN = "ZET HIER je TOKEN VAN FLIGHTAWARE NEER"
AEROAPI_URL = "https://aeroapi.flightaware.com/aeroapi/flights/"

# === Logging instellen ===
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


# === Operatornamen laden uit CSV ===
def laad_operator_namen(csv_pad):
    operator_dict = {}
    try:
        with open(csv_pad, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                icao = row['ICAO'].strip().upper()
                naam = row['Naam'].strip()
                operator_dict[icao] = naam
        logging.info(f"Operator-namen geladen uit {csv_pad}")
    except Exception as e:
        logging.error(f"Fout bij laden van {csv_pad}: {e}")
    return operator_dict

OPERATOR_NAMEN = laad_operator_namen(SCRIPT_DIR / "ICAO codes.csv")

# === Hulpfuncties ===
def wacht_op_aircraft_url(url, timeout=60):
    """Wacht tot de aircraft JSON bereikbaar is."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                logging.info("AIRCRAFT_URL bereikbaar.")
                return True
        except:
            pass
        time.sleep(2)
    logging.error("AIRCRAFT_URL niet bereikbaar binnen timeout.")
    return False

def in_gebied(lat, lon):
    return MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON

def haal_vluchtinfo_op(callsign):
    vertrek = "Onbekend"
    bestemming = "Onbekend"
    maatschappij = "Onbekend"

    try:
        clean_callsign = callsign.strip().upper()
        headers = {"x-apikey": AEROAPI_TOKEN}
        url = f"{AEROAPI_URL}{clean_callsign}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if "flights" in data and data["flights"]:
                vlucht = data["flights"][0]
                vertrek = vlucht.get("origin", {}).get("city", "Onbekend")
                bestemming = vlucht.get("destination", {}).get("city", "Onbekend")
                operator_code = vlucht.get("operator", "???")
                maatschappij = OPERATOR_NAMEN.get(operator_code, operator_code)
        else:
            logging.warning(f"API gaf status {response.status_code} voor {callsign}")
    except Exception as e:
        logging.error(f"Fout bij ophalen vluchtinfo: {e}")

    return vertrek, bestemming, maatschappij

# === GUI Klasse ===
class ScrollingImageApp:
    def __init__(self, root, callsign_queue):
        self.root = root
        self.callsign_queue = callsign_queue

        self.root.overrideredirect(True)
        self.root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}+0+0")

        self.canvas = tk.Canvas(root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, highlightthickness=0)
        self.canvas.pack()

        self.image = Image.open(IMAGE_FILE)
        self.image_width, self.image_height = self.image.size
        if self.image_height != SCREEN_HEIGHT or self.image_width < SCREEN_WIDTH:
            raise ValueError("Afbeelding moet exact 450px hoog zijn en minstens zo breed als het scherm.")

        self.double_image = Image.new('RGBA', (self.image_width * 2, self.image_height))
        self.double_image.paste(self.image, (0, 0))
        self.double_image.paste(self.image, (self.image_width, 0))

        self.offset = 0.0
        cropped = self.double_image.crop((0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        self.tk_image = ImageTk.PhotoImage(cropped)
        self.image_item = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.logo_item = None
        self.current_logo = None
        self.last_update_time = 0

        self.update_image()
        self.check_callsign_queue()
        self.root.bind('<Escape>', self.close)

    def close(self, event=None):
        self.root.destroy()

    def update_image(self):
        self.offset += SCROLL_SPEED
        if self.offset >= self.image_width:
            self.offset -= self.image_width
        x = int(self.offset)
        cropped = self.double_image.crop((x, 0, x + SCREEN_WIDTH, SCREEN_HEIGHT))
        self.tk_image = ImageTk.PhotoImage(cropped)
        self.canvas.itemconfig(self.image_item, image=self.tk_image)
        self.root.after(FRAME_DELAY, self.update_image)

    def draw_callsign_text(self, text):
        x = SCREEN_WIDTH // 2
        y = SCREEN_HEIGHT // 2 + 50
        font = ("Arial", 24, "bold")
        offset = 1
        for dx in [-offset, 0, offset]:
            for dy in [-offset, 0, offset]:
                if dx != 0 or dy != 0:
                    self.canvas.create_text(
                        x + dx, y + dy, text=text, fill="black",
                        font=font, anchor="center", tags="callsign_text"
                    )
        self.canvas.create_text(
            x, y, text=text, fill="white", font=font,
            anchor="center", tags="callsign_text"
        )

    def update_callsign(self, new_text, logo_image=None):
        self.canvas.delete("callsign_text")
        if self.logo_item:
            self.canvas.delete(self.logo_item)
            self.logo_item = None
            self.current_logo = None
        if new_text:
            self.draw_callsign_text(new_text)
            self.last_update_time = time.time()
            if logo_image:
                x = SCREEN_WIDTH // 2
                y = SCREEN_HEIGHT // 2 - 60
                self.logo_item = self.canvas.create_image(x, y, image=logo_image, anchor="center")
                self.current_logo = logo_image
        else:
            self.last_update_time = 0

    def check_callsign_queue(self):
        updated = False
        try:
            while True:
                text, logo_image = self.callsign_queue.get_nowait()
                self.update_callsign(text, logo_image)
                updated = True
        except queue.Empty:
            pass
        if not updated and self.last_update_time and (time.time() - self.last_update_time > 60):
            self.update_callsign("")
        self.root.after(1000, self.check_callsign_queue)

# === Aircraft monitor thread ===
def aircraft_monitor(callsign_queue):
    al_gemeld = set()
    al_gepiept = set()
    while True:
        try:
            response = requests.get(AIRCRAFT_URL)
            data = response.json()

            nieuw_callsign = ""
            logo_image = None

            for vliegtuig in data.get("aircraft", []):
                lat = vliegtuig.get("lat")
                lon = vliegtuig.get("lon")
                callsign = (vliegtuig.get("flight") or vliegtuig.get("flight_number") or "").strip()
                icao_code = callsign[:3].upper() if callsign else None

                if lat is None or lon is None:
                    continue

                if in_gebied(lat, lon) and callsign and callsign not in al_gemeld:
                    logging.info(f"✈️ Vliegtuig {callsign} in gebied!")
                    al_gemeld.add(callsign)
                    nieuw_callsign = callsign

                    if icao_code:
                        logo_path = LOGO_DIR / f"{icao_code}.png"
                        if logo_path.exists():
                            img = Image.open(logo_path)
                            img = img.resize((100, 100), Image.Resampling.LANCZOS)
                            logo_image = ImageTk.PhotoImage(img)
                    break

            if nieuw_callsign:
                vertrek, bestemming, maatschappij = haal_vluchtinfo_op(nieuw_callsign)
                weergave = f"{nieuw_callsign} ({maatschappij})\n{vertrek} → {bestemming}"
                logging.info(weergave)
                callsign_queue.put((weergave, logo_image))
                if nieuw_callsign not in al_gepiept:
                    os.system(f"mpg123 -q {PING_FILE} &")
                    al_gepiept.add(nieuw_callsign)

            time.sleep(5)

        except Exception as e:
            logging.error(f"Fout bij ophalen data: {e}")
            time.sleep(10)

# === Main ===
if __name__ == "__main__":
    if not wacht_op_aircraft_url(AIRCRAFT_URL):
        exit(1)

    callsign_queue = queue.Queue()
    root = tk.Tk()
    root.config(cursor="none")
    app = ScrollingImageApp(root, callsign_queue)

    monitor_thread = threading.Thread(target=aircraft_monitor, args=(callsign_queue,), daemon=True)
    monitor_thread.start()

    root.mainloop()
