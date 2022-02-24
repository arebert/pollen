import tkinter as tk
from PIL import Image
from PIL import ImageTk
from picamera import PiCamera
from picamera.array import PiRGBArray
import time
import cv2
import threading
import queue
from pathlib import Path
from datetime import datetime
from ctypes import *

# this lib is copied from https://github.com/ArduCAM/RaspberryPi/blob/master/Motorized_Focus_Camera
arducam_vcm =CDLL('./lib/libarducam_vcm.so')

ITEM_QUEUE_SZ = 200
ARDCAM_FOCUS_VAL = 350

class GUI:
    def __init__(self, master, queue):
        self.master = master
        self.master.title("Pollen")
        self.queue = queue
        self.lastImg = None
        self.pollenId = 0
        self.pollenSubId = 0

        self.imgLbl = tk.Label(self.master, bg="white")
        self.imgLbl.pack(side="top", expand=1, fill="both")

        btnFrm = tk.Frame(self.master, pady=10)
        btnFrm.pack(side="bottom")

        btn = tk.Button(btnFrm, text="Snapshot", command = self.takeSnapshot)
        btn.grid(column=0, row=0, padx=10)
        self.nextBtn = tk.Button(btnFrm, text="Next", command = self.nextPollen, state=tk.DISABLED)
        self.nextBtn.grid(column=1, row=0)
        self.pollenIdLbl = tk.Label(btnFrm, text=f"{self.pollenId}")
        self.pollenIdLbl.grid(column=2, row=0, padx=30)

        self.focusVar = tk.IntVar()
        self.focusVar.set(ARDCAM_FOCUS_VAL)
        camFocusSpinBox = tk.Spinbox(btnFrm, from_=0, to=1023,
            command = self.changeCamFocus, textvariable=self.focusVar,
            increment=10)
        camFocusSpinBox.grid(column=3, row=0, padx=30)

        self.imgPath = Path(datetime.now().strftime('%Y%m%d_%H%M%S'))
        self.imgPath.mkdir(parents=True, exist_ok=True)

        self.master.after(10, self.processQueue)

    def takeSnapshot(self):
        if self.lastImg is not None:

            p = str(self.imgPath / f"p{self.pollenId}_{self.pollenSubId}.jpg")
            cv2.imwrite(p, self.lastImg)
            self.pollenSubId += 1
            self.nextBtn["state"] = tk.NORMAL

    def changeCamFocus(self):
        print(f"Change focus {self.focusVar.get()}")
        print(f"camera.shutter_speed={camera.shutter_speed}")
        print(f"camera.iso={camera.iso}")
        arducam_vcm.vcm_write(self.focusVar.get())

    def nextPollen(self):
        self.pollenId += 1
        self.pollenSubId = 0
        self.pollenIdLbl.configure(text=f"{self.pollenId}")
        self.nextBtn["state"] = tk.DISABLED

    def processQueue(self):

        while not self.queue.empty():
            img = self.queue.get()
            self.lastImg = img.copy()
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            #lblW = self.imgLbl.winfo_width()
            #lblH = self.imgLbl.winfo_height()
            #iW = img.shape[1]
            #iH = img.shape[0]
            #wRatio= iW/lblW
            #hRatio = iH/lblH
            wRatio= img.shape[1]/self.imgLbl.winfo_width()
            hRatio = img.shape[0]/self.imgLbl.winfo_height()
            ratio = max(wRatio, hRatio)
            # round up to one decimal
            ratio = round(ratio, 1)

            if ratio > 0:
                width = int(img.shape[1]/ratio)
                height = int(img.shape[0]/ratio)
                img = cv2.resize(img, (width, height))

            im = Image.fromarray(img)
            im = ImageTk.PhotoImage(image=im)
            self.imgLbl.configure(image=im)
            self.imgLbl.image = im

        self.master.after(10, self.processQueue)

class CameraThread(threading.Thread):
    def __init__(self, queue, camera):
        super(CameraThread, self).__init__()
        self.queue = queue
        self.camera = camera

    def run(self):
        time.sleep(3)
        rawCapture = PiRGBArray(camera)

        for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=False):
            img = frame.array
            self.queue.put_nowait(img)
            rawCapture.truncate(0)

def getPiCam():
    # https://picamera.readthedocs.io/en/release-1.12/fov.html

    camera = PiCamera()
    # for Cam V1/Arducam B0176 (OV5647) full sensor area resolutions
    # - 2592x1944, 1296x972, 640x480
    #
    # for Cam V2 (IMX219)
    # - 3280x2464, 1640x1232
    camera.resolution = (2592, 1944)
    camera.shutter_speed = 50000

    time.sleep(2)

    return camera


arducam_vcm.vcm_init()

itemQueue = queue.Queue(ITEM_QUEUE_SZ)
root = tk.Tk()
root.geometry('1024x768')
mainUi = GUI(root, itemQueue)

camera = getPiCam()
arducam_vcm.vcm_write(ARDCAM_FOCUS_VAL)
cameraThread = CameraThread(itemQueue, camera)
cameraThread.start()

root.mainloop()

