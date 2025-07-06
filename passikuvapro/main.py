import cv2
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import os
import time
import json

SETTINGS_FILE = "settings.json"
DEFAULT_DIMENSIONS = (500, 653)

class PassportPhotoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Passport Photo Tool")

        self.frame = tk.Frame(root)
        self.frame.pack()

        self.canvas = tk.Canvas(self.frame, width=500, height=653)
        self.canvas.grid(row=0, column=0, columnspan=6)

        self.capture_button = tk.Button(self.frame, text="Capture", command=self.capture_image)
        self.capture_button.grid(row=1, column=0)

        # Movement buttons (hidden initially)
        self.move_left_button = tk.Button(self.frame, text="←", command=lambda: self.move_image(-5, 0))
        self.move_left_button.grid(row=1, column=1)
        self.move_left_button.grid_remove()

        self.move_right_button = tk.Button(self.frame, text="→", command=lambda: self.move_image(5, 0))
        self.move_right_button.grid(row=1, column=2)
        self.move_right_button.grid_remove()

        self.move_up_button = tk.Button(self.frame, text="↑", command=lambda: self.move_image(0, -5))
        self.move_up_button.grid(row=1, column=3)
        self.move_up_button.grid_remove()

        self.move_down_button = tk.Button(self.frame, text="↓", command=lambda: self.move_image(0, 5))
        self.move_down_button.grid(row=1, column=4)
        self.move_down_button.grid_remove()

        # Rotation buttons now rotate by 1 degree for microadjustment (hidden initially)
        self.rotate_left_button = tk.Button(self.frame, text="↺", command=lambda: self.rotate_image(-1))
        self.rotate_left_button.grid(row=2, column=0)
        self.rotate_left_button.grid_remove()

        self.rotate_right_button = tk.Button(self.frame, text="↻", command=lambda: self.rotate_image(1))
        self.rotate_right_button.grid(row=2, column=1)
        self.rotate_right_button.grid_remove()

        self.zoom_scale = tk.Scale(self.frame, from_=1.0, to=2.0, resolution=0.01, orient=tk.HORIZONTAL, label="Zoom")
        self.zoom_scale.set(1.0)
        self.zoom_scale.grid(row=2, column=2, columnspan=2, sticky="ew")
        self.zoom_scale.grid_remove()

        self.greyscale_var = tk.BooleanVar()
        self.greyscale_check = tk.Checkbutton(self.frame, text="Greyscale", variable=self.greyscale_var)
        self.greyscale_check.grid(row=2, column=4)
        self.greyscale_check.grid_remove()

        self.save_button = tk.Button(self.frame, text="Save", command=self.save_image)
        self.save_button.grid(row=1, column=5)

        self.settings_button = tk.Button(self.frame, text="Settings", command=self.open_settings)
        self.settings_button.grid(row=2, column=5)

        self.load_settings()
        self.load_overlay_image()

        self.cap = cv2.VideoCapture(0)
        self.captured_frame = None
        self.zoom = 1.0
        self.angle = 0
        self.offset_x = 0  # X offset for moving image after freeze
        self.offset_y = 0  # Y offset for moving image after freeze

        self.is_frozen = False  # Track whether frame is frozen
        self.current_frame = None
        self.update_frame()

    def load_settings(self):
        default_settings = {
            "overlay_path": "overlay.png",
            "opacity": 100,
            "output_size": list(DEFAULT_DIMENSIONS),
            "output_folder": os.getcwd()
        }

        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
            for key, value in default_settings.items():
                if key not in settings:
                    settings[key] = value
        else:
            settings = default_settings

        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)

        self.overlay_path = settings["overlay_path"]
        self.opacity = settings["opacity"]
        self.output_size = tuple(settings["output_size"])
        self.output_folder = settings["output_folder"]

    def load_overlay_image(self):
        self.overlay_img = cv2.imread(self.overlay_path, cv2.IMREAD_UNCHANGED)
        if self.overlay_img is None:
            messagebox.showerror("Error", f"Overlay image not found:\n{self.overlay_path}\nUsing transparent overlay instead.")
            self.overlay_img = np.zeros((self.output_size[1], self.output_size[0], 4), dtype=np.uint8)
        else:
            self.overlay_img = cv2.resize(self.overlay_img, self.output_size)

    def update_frame(self):
        if not self.is_frozen:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame.copy()
            else:
                self.current_frame = None

        if self.current_frame is not None:
            frame = self.apply_transformations(self.current_frame)
            preview = self.overlay_on_frame(frame.copy())
            self.display_image(preview)

        self.root.after(10, self.update_frame)

    def apply_transformations(self, frame):
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame)

        if self.is_frozen:
            zoom = self.zoom_scale.get()
        else:
            zoom = 1.0  # No zoom before capture

        w, h = pil_image.size
        pil_image = pil_image.resize((int(w * zoom), int(h * zoom)), Image.Resampling.LANCZOS)

        # Rotate by self.angle degrees, with expand to avoid cropping
        pil_image = pil_image.rotate(self.angle, expand=True)

        # After rotation, apply offset adjustments for movement (only after capture)
        if self.is_frozen:
            # Calculate crop box with offset_x and offset_y
            w, h = pil_image.size
            target_w, target_h = self.output_size
            cx, cy = w // 2 + self.offset_x, h // 2 + self.offset_y
            box = (cx - target_w // 2, cy - target_h // 2, cx + target_w // 2, cy + target_h // 2)
            pil_image = pil_image.crop(box)
        else:
            # Just crop center without offset
            w, h = pil_image.size
            target_w, target_h = self.output_size
            cx, cy = w // 2, h // 2
            box = (cx - target_w // 2, cy - target_h // 2, cx + target_w // 2, cy + target_h // 2)
            pil_image = pil_image.crop(box)

        if self.is_frozen and self.greyscale_var.get():
            pil_image = pil_image.convert("L").convert("RGB")

        return np.array(pil_image)

    def overlay_on_frame(self, frame):
        overlay = cv2.cvtColor(self.overlay_img, cv2.COLOR_BGRA2RGBA) if self.overlay_img.shape[2] == 4 else self.overlay_img
        alpha = self.opacity / 100.0

        if overlay.shape[2] == 4:
            overlay_rgb = overlay[:, :, :3]
        else:
            overlay_rgb = overlay

        overlay_resized = cv2.resize(overlay_rgb, (frame.shape[1], frame.shape[0]))

        if frame.shape[2] != overlay_resized.shape[2]:
            if overlay_resized.shape[2] == 4:
                overlay_resized = cv2.cvtColor(overlay_resized, cv2.COLOR_BGRA2BGR)
            elif overlay_resized.shape[2] == 1:
                overlay_resized = cv2.cvtColor(overlay_resized, cv2.COLOR_GRAY2BGR)

        blended = cv2.addWeighted(frame, 1, overlay_resized, alpha, 0)
        return blended

    def display_image(self, img):
        img = Image.fromarray(img)
        imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor="nw", image=imgtk)

    def capture_image(self):
        if self.current_frame is not None:
            self.captured_frame = self.current_frame.copy()
            self.is_frozen = True
            self.offset_x = 0
            self.offset_y = 0
            self.angle = 0
            self.zoom_scale.set(1.0)
            self.greyscale_var.set(False)
            self.show_edit_buttons(True)
            messagebox.showinfo("Captured", "Image captured and preview frozen!")
        else:
            messagebox.showerror("Error", "No frame available to capture.")

    def show_edit_buttons(self, show):
        if show:
            self.move_left_button.grid()
            self.move_right_button.grid()
            self.move_up_button.grid()
            self.move_down_button.grid()
            self.rotate_left_button.grid()
            self.rotate_right_button.grid()
            self.zoom_scale.grid()
            self.greyscale_check.grid()
        else:
            self.move_left_button.grid_remove()
            self.move_right_button.grid_remove()
            self.move_up_button.grid_remove()
            self.move_down_button.grid_remove()
            self.rotate_left_button.grid_remove()
            self.rotate_right_button.grid_remove()
            self.zoom_scale.grid_remove()
            self.greyscale_check.grid_remove()

    def move_image(self, dx, dy):
        if self.is_frozen:
            self.offset_x += dx
            self.offset_y += dy

    def rotate_image(self, degrees):
        if self.is_frozen:
            self.angle = (self.angle + degrees) % 360

    def save_image(self):
        if self.captured_frame is None:
            messagebox.showerror("Error", "No image captured.")
            return

        transformed = self.apply_transformations(self.captured_frame)
        output = Image.fromarray(transformed)
        filename = f"passport_{int(time.time())}.jpg"
        output.save(os.path.join(self.output_folder, filename))
        messagebox.showinfo("Saved", f"Image saved as {filename}")

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")

        tk.Label(win, text="Overlay Image").grid(row=0, column=0)
        overlay_path_entry = tk.Entry(win)
        overlay_path_entry.insert(0, self.overlay_path)
        overlay_path_entry.grid(row=0, column=1)
        tk.Button(win, text="Browse", command=lambda: self.browse_file(overlay_path_entry)).grid(row=0, column=2)

        tk.Label(win, text="Opacity").grid(row=1, column=0)
        opacity_scale = tk.Scale(win, from_=0, to=100, orient=tk.HORIZONTAL)
        opacity_scale.set(self.opacity)
        opacity_scale.grid(row=1, column=1, columnspan=2)

        tk.Label(win, text="Output Size (WxH)").grid(row=2, column=0)
        width_entry = tk.Entry(win, width=6)
        width_entry.insert(0, self.output_size[0])
        width_entry.grid(row=2, column=1)
        height_entry = tk.Entry(win, width=6)
        height_entry.insert(0, self.output_size[1])
        height_entry.grid(row=2, column=2)

        tk.Label(win, text="Output Folder").grid(row=3, column=0)
        folder_entry = tk.Entry(win)
        folder_entry.insert(0, self.output_folder)
        folder_entry.grid(row=3, column=1)
        tk.Button(win, text="Browse", command=lambda: self.browse_folder(folder_entry)).grid(row=3, column=2)

        tk.Button(win, text="Save", command=lambda: self.save_settings(
            overlay_path_entry.get(),
            opacity_scale.get(),
            (int(width_entry.get()), int(height_entry.get())),
            folder_entry.get(),
            win
        )).grid(row=4, column=0, columnspan=3)

    def browse_file(self, entry):
        path = filedialog.askopenfilename(filetypes=[("PNG Images", "*.png")])
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def browse_folder(self, entry):
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def save_settings(self, overlay_path, opacity, output_size, output_folder, window):
        settings = {
            "overlay_path": overlay_path,
            "opacity": opacity,
            "output_size": list(output_size),
            "output_folder": output_folder
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)

        self.overlay_path = overlay_path
        self.opacity = opacity
        self.output_size = output_size
        self.output_folder = output_folder

        self.load_overlay_image()
        window.destroy()
        messagebox.showinfo("Settings", "Settings saved.")

def main():
    root = tk.Tk()
    app = PassportPhotoApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
