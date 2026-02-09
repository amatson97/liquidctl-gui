"""GTK UI helper mixin for liquidctl-gui."""

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
except Exception:
    Gtk = None


class UiHelpers:
    def add_row(self, container):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        container.pack_start(row, False, False, 0)
        return row

    def add_label(self, container, text):
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        container.pack_start(label, False, False, 0)
        return label

    def add_section_label(self, container, text):
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_margin_top(4)
        container.pack_start(label, False, False, 0)
        return label

    def add_button(self, container, text, callback):
        button = Gtk.Button(label=text)
        button.connect("clicked", lambda *_: callback())
        container.pack_start(button, False, False, 0)
        return button

    def add_combo(self, container, values, default):
        combo = Gtk.ComboBoxText()
        if not values:
            combo.append_text("n/a")
            combo.set_active(0)
            combo.set_sensitive(False)
        else:
            for value in values:
                combo.append_text(value)
            combo.set_active(values.index(default) if default in values else 0)
        container.pack_start(combo, False, False, 0)
        return combo

    def add_frame(self, container, title):
        frame = Gtk.Frame(label=title)
        frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        frame_box.set_border_width(6)
        frame.add(frame_box)
        container.pack_start(frame, False, False, 0)
        return frame_box

    def add_separator(self, container):
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        container.pack_start(sep, False, False, 6)
        return sep

    def add_scale(self, container, min_val, max_val, value):
        adjustment = Gtk.Adjustment(value=value, lower=min_val, upper=max_val, step_increment=1, page_increment=5)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
        scale.set_digits(0)
        scale.set_hexpand(True)
        container.pack_start(scale, False, False, 0)
        return scale

    def add_status_text(self, container, height=100):
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(height)  # Minimal starting height
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)  # Allow vertical expansion
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scroller.add(text_view)
        container.pack_start(scroller, True, True, 0)  # Expand to fill container
        return text_view, text_view.get_buffer(), scroller

    def choose_file(self, title, action, default_name=None):
        dialog = Gtk.FileChooserDialog(
            title=title,
            parent=self,
            action=action
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE if action == Gtk.FileChooserAction.SAVE else Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK
        )
        if default_name:
            dialog.set_current_name(default_name)
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()
        if response != Gtk.ResponseType.OK or not path:
            return None
        return path
