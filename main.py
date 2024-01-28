import customtkinter
import tkinter
from tkinter import ttk
import tkinter.filedialog
from tkintermapview import TkinterMapView
from exif import Image as Ex_Image
from PIL import ImageTk
from PIL import Image as Pil_Image
import os

customtkinter.set_default_color_theme("blue")


def decimal_coords(coords, ref):
    decimal_degrees = coords[0] + coords[1] / 60 + coords[2] / 3600
    if ref == "S" or ref == 'W':
        decimal_degrees = -decimal_degrees
    return decimal_degrees


class App(customtkinter.CTk):

    APP_NAME = "Map View Demo"
    WIDTH = 800
    HEIGHT = 500

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title(App.APP_NAME)
        self.geometry(f"{App.WIDTH}x{App.HEIGHT}")
        self.minsize(App.WIDTH, App.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # self.bind("<Command-q>", self.on_closing)
        # self.bind("<Command-w>", self.on_closing)
        self.createcommand('tk::mac::Quit', self.on_closing)

        # -- Menubar

        menubar = tkinter.Menu(self)

        file_menu = tkinter.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='File', menu=file_menu)
        file_menu.add_command(label='Open Image', command=self.on_open_image)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.on_closing)

        view_menu = tkinter.Menu(menubar, tearoff=0)
        appearance_menu = tkinter.Menu(menubar, tearoff=0)
        appearance_menu.add_radiobutton(
            label='Dark', command=lambda: customtkinter.set_appearance_mode('Dark'))
        appearance_menu.add_radiobutton(
            label='Light', command=lambda: customtkinter.set_appearance_mode('Light'))
        appearance_menu.add_radiobutton(
            label='System', command=lambda: customtkinter.set_appearance_mode('System'))
        view_menu.add_cascade(label='Appearance', menu=appearance_menu)
        menubar.add_cascade(label='View', menu=view_menu)

        self.config(menu=menubar)

        self.marker_list = dict()  # <treeview iid, marker>

        # --Theme ttk Treeview
        bg_color = self._apply_appearance_mode(
            customtkinter.ThemeManager.theme['CTkFrame']['fg_color'])
        text_color = self._apply_appearance_mode(
            customtkinter.ThemeManager.theme['CTkLabel']['text_color'])
        selected_color = self._apply_appearance_mode(
            customtkinter.ThemeManager.theme['CTkButton']['fg_color'])
        treestyle = ttk.Style()
        treestyle.theme_use('default')
        treestyle.configure('Treeview', background=bg_color,
                            foreground=text_color, fieldbackground=bg_color, borderwidth=0)
        treestyle.map('Treeview', background=[('selected', bg_color)], foreground=[
                      ('selected', selected_color)])

        def treeview_update_appearance(appearance):
            x = 0
            if appearance == 'Dark':
                x = 1

            background = customtkinter.ThemeManager.theme['CTkFrame']['fg_color'][x]
            text = customtkinter.ThemeManager.theme['CTkLabel']['text_color'][x]
            select = customtkinter.ThemeManager.theme['CTkButton']['fg_color'][x]
            treestyle.configure('Treeview', background=background,
                                foreground=text, fieldbackground=background)
            treestyle.map('Treeview', background=[
                          ('selected', background)], foreground=[('selected', select)])
        customtkinter.AppearanceModeTracker.add(treeview_update_appearance)

        self.bind('<<TreeviewSelect>>', lambda event: self.focus_set())

        # --Create two CtkFrames

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.frame_left = customtkinter.CTkFrame(
            master=self, width=150, corner_radius=0, fg_color=None)
        self.frame_left.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        self.frame_right = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_right.grid(row=0, column=1, rowspan=1,
                              pady=0, padx=0, sticky="nsew")

        # frame_left

        # set second row (treeview) to take up as much space as it can
        self.frame_left.grid_rowconfigure(2, weight=1)

        self.button_1 = customtkinter.CTkButton(master=self.frame_left,
                                                text='Set Marker',
                                                command=self.set_marker_event)
        self.button_1.grid(pady=(20, 0), padx=(20, 20), row=0, column=0)

        self.button_2 = customtkinter.CTkButton(master=self.frame_left,
                                                text='Clear Markers',
                                                command=self.clear_marker_event)
        self.button_2.grid(pady=(20, 0), padx=(20, 20), row=1, column=0)

        self.treeview = ttk.Treeview(self.frame_left, show='tree')
        self.treeview.grid(row=2, column=0, sticky='nsew')
        self.treeview.tag_bind(
            'item', '<<TreeviewSelect>>', self.on_item_select)

        # frame_right

        self.frame_right.grid_rowconfigure(1, weight=1)
        self.frame_right.grid_rowconfigure(0, weight=0)
        self.frame_right.grid_columnconfigure(0, weight=1)
        self.frame_right.grid_columnconfigure(1, weight=0)
        self.frame_right.grid_columnconfigure(2, weight=1)

        self.map_widget = TkinterMapView(self.frame_right, corner_radius=0)
        self.map_widget.grid(row=1, rowspan=1, column=0,
                             columnspan=3, sticky='nswe', padx=(0, 0), pady=(0, 0))

        self.entry = customtkinter.CTkEntry(self.frame_right,
                                            placeholder_text='type address')
        self.entry.grid(row=0, column=0, sticky='we', padx=(12, 0), pady=12)
        self.entry.bind('<Return>', self.search_event)

        self.button_5 = customtkinter.CTkButton(self.frame_right,
                                                text='Search',
                                                width=90,
                                                command=self.search_event)
        self.button_5.grid(row=0, column=1, sticky='w', padx=(12, 0), pady=12)

        # Set default values
        self.map_widget.set_address('taylorsville, utah')

    def search_event(self, event=None):
        self.map_widget.set_address(self.entry.get())

    def on_item_select(self, event=None):
        iid = self.treeview.selection()[0]
        # TODO: Handle that this might be a folder instead of a single item
        marker = self.marker_list[iid]
        self.map_widget.set_position(marker.position[0], marker.position[1])

    def set_marker_event(self):
        current_position = self.map_widget.get_position()
        iid = self.treeview.insert(
            '', tkinter.END, text=f'Marker {len(self.marker_list)}', tags='item')
        self.marker_list[iid] = self.map_widget.set_marker(
            current_position[0], current_position[1])

    def clear_marker_event(self):
        self.map_widget.delete_all_marker()
        for iid in self.marker_list:
            self.treeview.delete(iid)
        self.marker_list.clear()

    def change_map(self, new_map: str):
        if new_map == 'OpenStreetMap':
            self.map_widget.set_tile_server(
                'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png')
        elif new_map == 'Google normal':
            self.map_widget.set_tile_server(
                'https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga', max_zoom=22)
        elif new_map == 'Google sat':
            self.map_widget.set_tile_server(
                'https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga', max_zoom=22)

    def on_open_image(self):
        filename = tkinter.filedialog.askopenfilename(
            title='Open Image', filetypes=[('Image File', '*.jpg *.png')])
        if filename == '':
            print("Canceled")
            return

        print(filename)
        with open(filename, 'rb') as src:
            img = Ex_Image(src)
        if img.has_exif:
            try:
                coords = (decimal_coords(img.gps_latitude, img.gps_latitude_ref),
                          decimal_coords(img.gps_longitude, img.gps_longitude_ref))
            except:
                print('Image has no coords')
                return
        else:
            print('Image has no coords')
            return

        iid = self.treeview.insert(
            '', tkinter.END, text=os.path.basename(filename), tags='item')
        mark = self.map_widget.set_marker(
            coords[0], coords[1], image=ImageTk.PhotoImage(Pil_Image.open(filename).resize((100, 100))))
        self.marker_list[iid] = mark

        self.map_widget.set_position(coords[0], coords[1])

    def on_closing(self, event=0):
        self.destroy()

    def start(self):
        self.mainloop()


if __name__ == '__main__':
    app = App()
    app.start()
