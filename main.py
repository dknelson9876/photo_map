import customtkinter
import tkinter
from tkinter import ttk
import tkinter.filedialog
import tkintermapview
from tkintermapview import TkinterMapView
from exif import Image as Ex_Image
from PIL import ImageTk, ImageOps
from PIL import Image as Pil_Image
import os

customtkinter.set_default_color_theme("blue")
IMAGE_EXT = ('.jpg', '.jpeg', '.png')


def coords_dms_to_float(coords, ref):
    decimal_degrees = coords[0] + coords[1] / 60 + coords[2] / 3600
    if ref == "S" or ref == 'W':
        decimal_degrees = -decimal_degrees
    return decimal_degrees


def coords_float_to_dms(lat, long):
    def decimal_degrees_to_dms(value, is_lat):
        direction = 'N' if is_lat else 'E'
        if value < 0:
            direction = 'S' if is_lat else 'W'
            value = abs(value)
        deg = int(value)
        min = int((value - deg) * 60)
        sec = (value - deg - min / 60) * 3600

        return {
            'tup': (deg, min, sec),
            'ref': direction,
        }

    lat_dict = decimal_degrees_to_dms(lat, True)
    long_dict = decimal_degrees_to_dms(long, False)

    return {
        'lat': lat_dict,
        'long': long_dict,
    }


class App(customtkinter.CTk):

    APP_NAME = "Map View Demo"
    WIDTH = 800
    HEIGHT = 500

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title(App.APP_NAME)
        # self.geometry(f"{App.WIDTH}x{App.HEIGHT}")
        self.state('zoomed')
        self.minsize(App.WIDTH, App.HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # self.bind("<Command-q>", self.on_closing)
        # self.bind("<Command-w>", self.on_closing)
        # self.createcommand('tk::mac::Quit', self.on_closing)

        # -- Menubar

        menubar = tkinter.Menu(self)

        file_menu = tkinter.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='File', menu=file_menu)
        file_menu.add_command(label='Open Image', command=self.on_open_image)
        file_menu.add_command(label='Open Folder', command=self.on_open_folder)
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
        self.image_dict = dict()  # <treeview iid, absolute filepath>
        self.folders_dict = dict()  # <treeview iid, absolute folder path>

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

        self.frame_center = customtkinter.CTkFrame(
            master=self, corner_radius=0)
        self.frame_center.grid(row=0, column=1, rowspan=1,
                               pady=0, padx=0, sticky="nsew")

        self.frame_right = customtkinter.CTkFrame(
            master=self, width=150, corner_radius=0)
        self.frame_right.grid(row=0, column=2, pady=0, padx=0, sticky='nsew')

        # --frame_left

        # set second row (treeview) to take up as much space as it can
        self.frame_left.grid_rowconfigure(2, weight=1)

        self.set_mark_btn = customtkinter.CTkButton(master=self.frame_left,
                                                    text='Set Marker',
                                                    command=self.set_marker_event)
        self.set_mark_btn.grid(pady=(20, 0), padx=(20, 20), row=0, column=0)

        self.clear_mark_btn = customtkinter.CTkButton(master=self.frame_left,
                                                      text='Clear Markers',
                                                      command=self.on_clear_markers)
        self.clear_mark_btn.grid(pady=(20, 0), padx=(20, 20), row=1, column=0)

        self.treeview = ttk.Treeview(
            self.frame_left, columns=('city', 'lat', 'long'))
        self.treeview.heading('#0', text='Name')
        self.treeview.column('#0', minwidth=5, width=100)
        self.treeview.heading('city', text='City')
        self.treeview.column('city', minwidth=5, width=80)
        self.treeview.heading('lat', text='Lat')
        self.treeview.column('lat', minwidth=5, width=60)
        self.treeview.heading('long', text='Long')
        self.treeview.column('long', minwidth=5, width=60)
        self.treeview.grid(row=2, column=0, pady=(
            20, 0), padx=5, sticky='nsew')
        self.treeview.tag_bind(
            'item', '<<TreeviewSelect>>', self.on_item_select
        )
        self.treeview.tag_bind(
            'folder', '<<TreeviewOpen>>', self.on_item_expand
        )

        # --frame_center

        self.frame_center.grid_rowconfigure(1, weight=1)
        self.frame_center.grid_rowconfigure(0, weight=0)
        self.frame_center.grid_columnconfigure(0, weight=1)
        self.frame_center.grid_columnconfigure(1, weight=0)
        self.frame_center.grid_columnconfigure(2, weight=1)

        self.map_widget = TkinterMapView(self.frame_center, corner_radius=0)
        self.map_widget.grid(row=1, rowspan=1, column=0,
                             columnspan=3, sticky='nswe', padx=(0, 0), pady=(0, 0))
        self.map_widget.add_left_click_map_command(
            lambda coords: self.on_coord_select(coords))

        self.entry = customtkinter.CTkEntry(self.frame_center,
                                            placeholder_text='type address')
        self.entry.grid(row=0, column=0, sticky='we', padx=(12, 0), pady=12)
        self.entry.bind('<Return>', self.search_event)

        self.button_5 = customtkinter.CTkButton(self.frame_center,
                                                text='Search',
                                                width=90,
                                                command=self.search_event)
        self.button_5.grid(row=0, column=1, sticky='w', padx=(12, 0), pady=12)

        # --frame_right

        self.frame_right.grid_columnconfigure(0, weight=0)
        self.frame_right.grid_columnconfigure(1, weight=1)

        self.selected_label = customtkinter.CTkLabel(
            self.frame_right, text='Nothing selected')
        self.selected_label.grid(
            row=0, column=0, columnspan=2, sticky='ew', padx=5)

        self.lat_label = customtkinter.CTkLabel(self.frame_right, text='Lat:')
        self.lat_label.grid(row=1, column=0, padx=5)

        self.lat_str = tkinter.StringVar()
        self.lat_entry = customtkinter.CTkEntry(
            self.frame_right, placeholder_text='latitude...', textvariable=self.lat_str)
        self.lat_entry.grid(row=1, column=1, sticky='ew')

        self.long_label = customtkinter.CTkLabel(
            self.frame_right, text='Long:')
        self.long_label.grid(row=2, column=0, padx=5)

        self.long_str = tkinter.StringVar()
        self.long_entry = customtkinter.CTkEntry(
            self.frame_right, placeholder_text='longitude...', textvariable=self.long_str)
        self.long_entry.grid(row=2, column=1, sticky='ew')

        self.update_loc_btn = customtkinter.CTkButton(
            self.frame_right, text='Update Location', command=self.on_update_location)
        self.update_loc_btn.grid(row=3, column=0, columnspan=2, sticky='ew')

        self.img_preview = None
        self.img_holder = customtkinter.CTkLabel(self.frame_right, image=self.img_preview, text='')
        self.img_holder.grid(row=4, column=0, columnspan=2, sticky='ew')

        # Set default values
        self.map_widget.set_address('taylorsville, utah')
        self.sel_coords = None

    def search_event(self, event=None):
        self.map_widget.set_address(self.entry.get())

    # Event listener for clicking an item in the treeview
    def on_item_select(self, event=None):
        iid = self.treeview.selection()[0]
        # TODO: Handle that this might be a folder instead of a single item
        if iid in self.marker_list:
            marker = self.marker_list[iid]
            self.map_widget.set_position(
                marker.position[0], marker.position[1])
            self.selected_label.configure(text=self.treeview.item(iid)['text'])
            self.lat_str.set(str(marker.position[0]))
            self.long_str.set(str(marker.position[1]))
        else:
            self.selected_label.configure(text=self.treeview.item(iid)['text'])
            self.lat_str.set('')
            self.long_str.set('')

        if iid in self.image_dict:
            img = Pil_Image.open(self.image_dict[iid])
            img.thumbnail((200, 200))
            self.img_preview = customtkinter.CTkImage(img, size=(200, 200))
            self.img_holder.configure(image=self.img_preview)

    def on_item_expand(self, event=None):
        iid = self.treeview.selection()[0]
        self.load_subitems(iid)

    # Event Listener for left click on the map

    def on_coord_select(self, coords):
        if self.sel_coords:
            self.sel_coords.set_position(coords[0], coords[1])
        else:
            self.sel_coords = self.map_widget.set_marker(
                coords[0],
                coords[1],
                marker_color_outside='blue',
                marker_color_circle='blue'
            )

    # Event Listener for the 'Update Location' button
    #  sets the coordinates of the currently selected item
    #  in the treeview to the location that is selected on the map
    # TODO: Escape to unselect a location on the map?
    def on_update_location(self, event=None):
        if self.sel_coords is None:
            return
        # TODO: Handle multiple things selected at once
        new_coords = self.sel_coords.position
        iid = self.treeview.selection()[0]

        # Update in treeview
        self.treeview.item(iid,
                           values=(tkintermapview.convert_coordinates_to_city(new_coords[0],
                                                                              new_coords[1]),
                                   new_coords[0],
                                   new_coords[1]
                                   )
                           )

        # Update on map
        if iid in self.marker_list:
            marker = self.marker_list[iid]
            marker.set_position(new_coords[0], new_coords[1])

        # Update image file
        if iid in self.image_dict:
            with open(self.image_dict[iid], 'rb') as image_file:
                img = Ex_Image(image_file)
            coord_dict = coords_float_to_dms(new_coords[0], new_coords[1])
            img.gps_latitude = coord_dict['lat']['tup']
            img.gps_latitude_ref = coord_dict['lat']['ref']
            img.gps_longitude = coord_dict['long']['tup']
            img.gps_longitude_ref = coord_dict['long']['ref']
            with open(self.image_dict[iid], 'wb') as image_file:
                image_file.write(img.get_file())

            # if pin was not already on map, add it now
            if iid not in self.marker_list:
                img = Pil_Image.open(self.image_dict[iid])
                img = ImageOps.contain(img, (100, 100))
                self.marker_list[iid] = self.map_widget.set_marker(
                    new_coords[0],
                    new_coords[1],
                    image=ImageTk.PhotoImage(img)
                )

    # Event Listener for the 'Set Marker' button
    def set_marker_event(self):
        new_pos = self.map_widget.get_position()
        iid = self.treeview.insert(
            '',
            tkinter.END,
            text=f'Marker {len(self.marker_list)}',
            tags='item',
            # place, lat, long
            values=(tkintermapview.convert_coordinates_to_city(new_pos[0],
                                                               new_pos[1]),
                    new_pos[0],
                    new_pos[1]
                    )
        )
        self.marker_list[iid] = self.map_widget.set_marker(
            new_pos[0], new_pos[1])

    # Event listener for the 'Clear Markers' button
    # Removes all markers from the map and all items from the treeview
    def on_clear_markers(self):
        self.map_widget.delete_all_marker()
        for iid in self.marker_list:
            self.treeview.delete(iid)
        self.sel_coords = None
        self.marker_list.clear()

    def insert_image(self, filename: str, parent=''):
        with open(filename, 'rb') as src:
            img = Ex_Image(src)
        if img.has_exif:
            try:
                coords = (coords_dms_to_float(img.gps_latitude, img.gps_latitude_ref),
                          coords_dms_to_float(img.gps_longitude, img.gps_longitude_ref))
            except:
                print('Image has no coords')
                iid = self.treeview.insert(
                    parent,
                    tkinter.END,
                    text=os.path.basename(filename),
                    tags=('item')
                )
                self.image_dict[iid] = filename
                return
        else:
            print('Image has no metadata')
            return

        # Add to treeview
        iid = self.treeview.insert(
            parent,
            tkinter.END,
            text=os.path.basename(filename),
            tags='item',
            values=(tkintermapview.convert_coordinates_to_city(
                coords[0], coords[1]), coords[0], coords[1])
        )

        # Add to map
        img = Pil_Image.open(filename)
        img.thumbnail((100, 100))
        mark = self.map_widget.set_marker(
            coords[0],
            coords[1],
            image=ImageTk.PhotoImage(img)
        )

        # store reference to map marker
        self.marker_list[iid] = mark
        # store reference to file
        self.image_dict[iid] = filename
        # center map on new marker
        self.map_widget.set_position(coords[0], coords[1])

    # Given a the path to a folder, load it into the treeview
    def load_tree(self, filepath, parent=''):
        for obj in os.listdir(filepath):
            objpath = os.path.join(filepath, obj)
            # if obj is an image, insert it on its own
            if obj.endswith(IMAGE_EXT):
                self.insert_image(objpath, parent)
            # if obj is a subfolder, insert it and it's children,
            #   so that it's expandable
            elif os.path.isdir(objpath):
                child_iid = self.insert_folder(objpath, parent)
                for subobj in os.listdir(objpath):
                    subobj_path = os.path.join(objpath, subobj)
                    if os.path.isdir(subobj_path):
                        self.insert_folder(subobj_path, child_iid)
                    elif subobj.endswith(IMAGE_EXT):
                        self.insert_image(subobj_path, child_iid)

    def load_subitems(self, iid):
        pass
        # for child_iid in self.treeview.get_children(iid):
        #     if child_iid in self.folders_dict:
        #         self.load_tree(self.folders_dict[child_iid],
        #                        parent=child_iid)

    def insert_folder(self, path, parent='') -> str:
        iid = self.treeview.insert(
            parent,
            tkinter.END,
            text=os.path.basename(path),
            tags='folder'
        )
        self.folders_dict[iid] = path
        return iid

    # Spawn a folder dialog to select a folder, then add that folder
    # as a new root item to the treeview
    def on_open_folder(self):
        filepath = tkinter.filedialog.askdirectory(
            title='Open Folder', mustexist=True)
        if filepath == '':
            print('Open folder operation canceled')
            return
        parent_iid = self.insert_folder(filepath)
        self.load_tree(filepath, parent_iid)

    # Event listener for the 'Open Image' option under the file menu
    #  Adds the opened image to the treeview, and if it has location metadata,
    #  to the map as well
    def on_open_image(self):
        filename = tkinter.filedialog.askopenfilename(
            title='Open Image', filetypes=[('Image File', '*.jpg *.png')])
        if filename == '':
            print('Canceled')
            return

        print(f'Opening {filename}')
        self.insert_image(filename)

    def on_closing(self, event=0):
        self.destroy()

    def start(self):
        self.mainloop()


if __name__ == '__main__':
    app = App()
    app.start()
